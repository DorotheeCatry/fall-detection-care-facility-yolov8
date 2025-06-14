"""
Système de suivi temporel des chutes pour déterminer le niveau d'urgence.
"""

import time
import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class FallState(Enum):
    """États possibles d'une personne détectée au sol."""
    MONITORING = "monitoring"      # 0-10s : surveillance
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
    
    def time_on_ground(self) -> float:
        """Retourne le temps passé au sol en secondes."""
        return time.time() - self.first_detected
    
    def update_movement(self, current_position: Tuple[int, int], threshold: int = 20) -> bool:
        """
        Détecte si la personne a bougé depuis la dernière position.
        
        Args:
            current_position: Position actuelle (x, y)
            threshold: Seuil de mouvement en pixels
            
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
        
        if time_elapsed > 30:  # Plus de 30 secondes
            if not self.movement_detected:
                return FallState.URGENT  # Immobile = urgent
            else:
                return FallState.ALERT   # Bouge mais longtemps au sol
        elif time_elapsed > 10:  # Entre 10 et 30 secondes
            return FallState.ALERT
        else:  # Moins de 10 secondes
            return FallState.MONITORING

class FallTracker:
    """Gestionnaire de suivi des chutes avec états temporels."""
    
    def __init__(self, timeout: float = 60.0):
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
            state.last_seen = current_time
            state.update_movement(current_position)
        
        # Calculer le niveau d'urgence
        state = self.person_states[person_id]
        urgency = state.get_urgency_level()
        state.current_state = urgency
        
        return urgency, state.time_on_ground()
    
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