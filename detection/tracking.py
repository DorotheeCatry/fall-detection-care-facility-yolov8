"""
Temporal fall tracking system to determine urgency level.
Enhanced version with persistence and tolerance to detection interruptions.
"""

import time
import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Description and intervention level for each state
STATE_DESCRIPTION_MAP = {
    "monitoring": {
        "description": "Normal person, monitoring",
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
    """Possible states of a person detected on the ground."""
    MONITORING = "monitoring"     # 0-10s: monitoring
    ALERT = "alert"               # 10-30s: standard alert  
    URGENT = "urgent"             # >30s: urgent alert
    RECOVERED = "recovered"       # person got up

@dataclass
class PersonState:
    """State of a tracked person."""
    first_detected: float
    last_seen: float
    last_position: Optional[Tuple[int, int]] = None
    movement_detected: bool = False
    current_state: FallState = FallState.MONITORING
    missed_detections: int = 0  # Counter for missed detections
    max_missed: int = 10        # Tolerance before abandoning
    
    def time_on_ground(self) -> float:
        """Returns time spent on ground in seconds."""
        return time.time() - self.first_detected
    
    def update_movement(self, current_position: Tuple[int, int], threshold: int = 30) -> bool:
        """
        Detects if the person has moved since last position.
        
        Args:
            current_position: Current position (x, y)
            threshold: Movement threshold in pixels (increased for more tolerance)
            
        Returns:
            True if movement detected
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
        """Determines urgency level based on time and movement."""
        time_elapsed = self.time_on_ground()
        
        # Once urgent, stays urgent even with intermittent detection
        if self.current_state == FallState.URGENT and time_elapsed > 25:
            return FallState.URGENT
        
        if time_elapsed > 30:  # More than 30 seconds
            if not self.movement_detected:
                return FallState.URGENT  # Immobile = urgent
            else:
                return FallState.ALERT   # Moving but long time on ground
        elif time_elapsed > 10:  # Between 10 and 30 seconds
            return FallState.ALERT
        else:  # Less than 10 seconds
            return FallState.MONITORING
    
    def mark_missed(self):
        """Marks a missed detection."""
        self.missed_detections += 1
    
    def mark_found(self):
        """Resets missed detection counter."""
        self.missed_detections = 0
        self.last_seen = time.time()
    
    def should_keep_alive(self) -> bool:
        """Determines if we should keep this tracking despite missed detections."""
        return self.missed_detections < self.max_missed

class FallTracker:
    """Fall tracking manager with temporal states."""
    
    def __init__(self, timeout: float = 120.0):  # 2 minutes
        """
        Args:
            timeout: Time after which a person is no longer tracked
        """
        self.person_states: Dict[str, PersonState] = {}
        self.timeout = timeout
        
    def update_detection(self, person_id: str, bbox: Tuple[int, int, int, int]) -> Tuple[FallState, float]:
        """
        Updates the state of a person detected on the ground.
        
        Args:
            person_id: Unique person identifier
            bbox: Bounding box (x1, y1, x2, y2)
            
        Returns:
            Tuple (current_state, time_on_ground)
        """
        current_time = time.time()
        
        # Center position of bounding box
        center_x = (bbox[0] + bbox[2]) // 2
        center_y = (bbox[1] + bbox[3]) // 2
        current_position = (center_x, center_y)
        
        if person_id not in self.person_states:
            # New detection
            self.person_states[person_id] = PersonState(
                first_detected=current_time,
                last_seen=current_time,
                last_position=current_position
            )
        else:
            # Update existing detection
            state = self.person_states[person_id]
            state.mark_found()  # Reset missed counter
            state.update_movement(current_position)
        
        # Calculate urgency level
        state = self.person_states[person_id]
        urgency = state.get_urgency_level()
        state.current_state = urgency
        
        return urgency, state.time_on_ground()
    
    def update_missed_detections(self):
        """
        Updates counters for people not detected in this frame.
        Call every frame even when YOLO detects nothing.
        """
        current_time = time.time()
        to_remove = []
        
        for person_id, state in self.person_states.items():
            # If not seen for more than 2 seconds, mark as missed
            if current_time - state.last_seen > 2.0:
                state.mark_missed()
                
                # If too many misses, remove
                if not state.should_keep_alive():
                    to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.person_states[person_id]
    
    def get_persistent_states(self) -> Dict[str, PersonState]:
        """
        Returns persistent states even without recent detection.
        To maintain display even when YOLO misses some frames.
        """
        current_time = time.time()
        active_states = {}
        
        for person_id, state in self.person_states.items():
            # Keep recent or urgent states
            time_since_last_seen = current_time - state.last_seen
            if (time_since_last_seen < 5.0 or  # Seen recently
                state.current_state == FallState.URGENT):  # Or urgent
                active_states[person_id] = state
                
        return active_states
    
    def get_state_info(self, state_str: str) -> dict:
        """
        Returns description and intervention level for a given state.
        """
        return STATE_DESCRIPTION_MAP.get(state_str, {
            "description": "Unknown state",
            "needs_help": "Unknown",
            "level": "❓ Unknown"
        })
    
    def get_state_label(self, person_id: str) -> str:
        """
        Returns a readable label for screen display.
        """
        state_obj = self.person_states.get(person_id)
        if state_obj:
            state_str = state_obj.current_state.value  # "monitoring", "alert", etc.
            info = self.get_state_info(state_str)
            level = info.get("level", "")
            time_elapsed = int(state_obj.time_on_ground())
            return f"{level} ({time_elapsed}s)"
        return "❓ Unknown"
    
    def get_state_color(self, person_id: str) -> Tuple[int, int, int]:
        """
        Returns BGR color for OpenCV display based on state.
        """
        state_obj = self.person_states.get(person_id)
        if not state_obj:
            return (128, 128, 128)  # Gray for unknown
        
        color_map = {
            FallState.MONITORING: (0, 255, 255),    # Yellow (BGR)
            FallState.ALERT: (0, 165, 255),         # Orange (BGR)
            FallState.URGENT: (0, 0, 255),          # Red (BGR)
            FallState.RECOVERED: (0, 255, 0),       # Green (BGR)
        }
        return color_map.get(state_obj.current_state, (128, 128, 128))
    
    def cleanup_old_tracks(self):
        """Removes old tracks."""
        current_time = time.time()
        to_remove = []
        
        for person_id, state in self.person_states.items():
            if current_time - state.last_seen > self.timeout:
                to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.person_states[person_id]
    
    def get_active_states(self) -> Dict[str, PersonState]:
        """Returns all active states."""
        self.cleanup_old_tracks()
        return self.person_states.copy()
    
    def has_urgent_cases(self) -> bool:
        """Checks if there are urgent cases."""
        return any(
            state.current_state == FallState.URGENT 
            for state in self.person_states.values()
        )

# Global tracker instance
fall_tracker = FallTracker()