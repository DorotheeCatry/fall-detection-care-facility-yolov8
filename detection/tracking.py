"""
Système de suivi temporel des chutes pour déterminer le niveau d'urgence.
Version améliorée avec persistance et tolérance aux interruptions.
"""

import time
import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Description et niveau de besoin d'intervention pour chaque état
STATE_DESCRIPTION_MAP = {
    "monitoring": {
        "description": "Person has gotten up, monitoring",
        "needs_help": False,
        "level": "🟡 Monitoring"
    },
    "alert": {
        "description": "Person has been on the ground for a while",
        "needs_help": "Potentially",
        "level": "🟠 Alert"
    },
    "urgent": {
        "description": "Person immobile on the ground for a long time",
        "needs_help": True,
        "level": "🔴 Urgent Alert"
    },
    "recovered": {
        "description": "Person got up by themselves",
        "needs_help": False,
        "level": "🟢 Recovered"
    },
}

class FallState(Enum):
    """États possibles d'une personne détectée au sol."""
    MONITORING = "monitoring"     # 0-10s : surveillance
    ALERT = "alert"               # 10-30s : alerte standard  
    URGENT = "urgent"             # >30s : alerte urgente
    RECOVERED = "recovered"       # personne s'est relevée

@dataclass
class PersonState:
    """État d'une personne suivie."""
    first_detected: float
    last_seen: float
    last_position: Optional[Tuple[int, int]] = None
    movement_detected: bool = False
    current_state: FallState = FallState.MONITORING
    missed_detections: int = 0  # Compteur de détections ratées
    max_missed: int = 10        # Tolérance avant abandon
    
    def time_on_ground(self) -> float:
        """Retourne le temps passé au sol en secondes."""
        return time.time() - self.first_detected
    
    def update_movement(self, current_position: Tuple[int, int], threshold: int = 30) -> bool:
        """
        Détecte si la personne a bougé depuis la dernière position.
        
        Args:
            current_position: Position actuelle (x, y)
            threshold: Seuil de mouvement en pixels (augmenté pour plus de tolérance)
            
        Returns:
            True si mouvement détecté
        """
        if self.last_position is None:
            self.last_position = current_position
            return False
            
        distance = np.sqrt(
            (current_position[0] - self.last_position[0])**2 + 
            (current_position[1] - self.last_position[1])**2
        )
        
        moved = distance > threshold
        if moved:
            self.movement_detected = True
            self.last_position = current_position
            
        return moved
    
    def get_urgency_level(self) -> FallState:
        """Détermine le niveau d'urgence basé sur le temps et le mouvement."""
        time_elapsed = self.time_on_ground()
        
        # Une fois urgent, reste urgent même si détection intermittente
        if self.current_state == FallState.URGENT and time_elapsed > 25:
            return FallState.URGENT
        
        if time_elapsed > 30:  # Plus de 30 secondes
            if not self.movement_detected:
                return FallState.URGENT  # Immobile = urgent
            else:
                return FallState.ALERT   # Bouge mais longtemps au sol
        elif time_elapsed > 10:  # Entre 10 et 30 secondes
            return FallState.ALERT
        else:  # Moins de 10 secondes
            return FallState.MONITORING
    
    def mark_missed(self):
        """Marque une détection ratée."""
        self.missed_detections += 1
    
    def mark_found(self):
        """Remet à zéro le compteur de détections ratées."""
        self.missed_detections = 0
        self.last_seen = time.time()
    
    def should_keep_alive(self) -> bool:
        """Détermine si on doit garder ce tracking malgré les détections ratées."""
        return self.missed_detections < self.max_missed

class FallTracker:
    """Gestionnaire de suivi des chutes avec états temporels."""
    
    def __init__(self, timeout: float = 120.0):  # 2 minutes
        """
        Args:
            timeout: Temps après lequel on considère qu'une personne n'est plus suivie
        """
        self.person_states: Dict[str, PersonState] = {}
        self.timeout = timeout
        
    def update_detection(self, person_id: str, bbox: Tuple[int, int, int, int]) -> Tuple[FallState, float]:
        """
        Met à jour l'état d'une personne détectée au sol.
        
        Args:
            person_id: Identifiant unique de la personne
            bbox: Bounding box (x1, y1, x2, y2)
            
        Returns:
            Tuple (état_actuel, temps_au_sol)
        """
        current_time = time.time()
        
        # Position centrale de la bounding box
        center_x = (bbox[0] + bbox[2]) // 2
        center_y = (bbox[1] + bbox[3]) // 2
        current_position = (center_x, center_y)
        
        if person_id not in self.person_states:
            # Nouvelle détection
            self.person_states[person_id] = PersonState(
                first_detected=current_time,
                last_seen=current_time,
                last_position=current_position
            )
        else:
            # Mise à jour d'une détection existante
            state = self.person_states[person_id]
            state.mark_found()  # Remet à zéro le compteur de ratés
            state.update_movement(current_position)
        
        # Calculer le niveau d'urgence
        state = self.person_states[person_id]
        urgency = state.get_urgency_level()
        state.current_state = urgency
        
        return urgency, state.time_on_ground()
    
    def update_missed_detections(self):
        """
        Met à jour les compteurs pour les personnes non détectées dans cette frame.
        À appeler à chaque frame même quand YOLO ne détecte rien.
        """
        current_time = time.time()
        to_remove = []
        
        for person_id, state in self.person_states.items():
            # Si pas vu depuis plus de 2 secondes, marquer comme raté
            if current_time - state.last_seen > 2.0:
                state.mark_missed()
                
                # Si trop de ratés, supprimer
                if not state.should_keep_alive():
                    to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.person_states[person_id]
    
    def get_persistent_states(self) -> Dict[str, PersonState]:
        """
        Retourne les états persistants même sans détection récente.
        Pour maintenir l'affichage même quand YOLO rate quelques frames.
        """
        current_time = time.time()
        active_states = {}
        
        for person_id, state in self.person_states.items():
            # Garder les états récents ou urgents
            time_since_last_seen = current_time - state.last_seen
            if (time_since_last_seen < 5.0 or  # Vu récemment
                state.current_state == FallState.URGENT):  # Ou urgent
                active_states[person_id] = state
                
        return active_states
    
    def get_state_info(self, state_str: str) -> dict:
        """
        Retourne la description et le niveau d'intervention d'un état donné.
        """
        return STATE_DESCRIPTION_MAP.get(state_str, {
            "description": "État inconnu",
            "needs_help": "Inconnu",
            "level": "❓ Inconnu"
        })
    
    def get_state_label(self, person_id: str) -> str:
        """
        Retourne un label lisible pour affichage à l'écran.
        """
        state_obj = self.person_states.get(person_id)
        if state_obj:
            state_str = state_obj.current_state.value  # "monitoring", "alert", etc.
            info = self.get_state_info(state_str)
            level = info.get("level", "")
            time_elapsed = int(state_obj.time_on_ground())
            return f"{level} ({time_elapsed}s)"
        return "❓ Inconnu"
    
    def get_state_color(self, person_id: str) -> Tuple[int, int, int]:
        """
        Retourne la couleur BGR pour l'affichage OpenCV selon l'état.
        """
        state_obj = self.person_states.get(person_id)
        if not state_obj:
            return (128, 128, 128)  # Gris pour inconnu
        
        color_map = {
            FallState.MONITORING: (0, 255, 255),    # Jaune (BGR)
            FallState.ALERT: (0, 165, 255),         # Orange (BGR)
            FallState.URGENT: (0, 0, 255),          # Rouge (BGR)
            FallState.RECOVERED: (0, 255, 0),       # Vert (BGR)
        }
        return color_map.get(state_obj.current_state, (128, 128, 128))
    
    def cleanup_old_tracks(self):
        """Supprime les suivis trop anciens."""
        current_time = time.time()
        to_remove = []
        
        for person_id, state in self.person_states.items():
            if current_time - state.last_seen > self.timeout:
                to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.person_states[person_id]
    
    def get_active_states(self) -> Dict[str, PersonState]:
        """Retourne tous les états actifs."""
        self.cleanup_old_tracks()
        return self.person_states.copy()
    
    def has_urgent_cases(self) -> bool:
        """Vérifie s'il y a des cas urgents."""
        return any(
            state.current_state == FallState.URGENT 
            for state in self.person_states.values()
        )

# Instance globale du tracker
fall_tracker = FallTracker()