"""
Knowledge Capsule Lifecycle Tracker
Tracks knowledge through stages: sprout → green_leaf → yellow_leaf → red_leaf → soil
"""

from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime
import time

class CapsulePhase(Enum):
    SPROUT = "sprout"      # 萌芽 - newly learned
    GREEN_LEAF = "green_leaf"  # 绿叶 - actively used
    YELLOW_LEAF = "yellow_leaf" # 黄叶 - occasionally used
    RED_LEAF = "red_leaf"    # 枯叶 - rarely used
    SOIL = "soil"           # 土壤 - archived

class CapsuleLifecycle:
    """
    Tracks knowledge capsule lifecycle with confidence-based phase transitions.
    Based on Memory-Like-A-Tree concept.
    """
    
    PHASE_THRESHOLDS = {
        CapsulePhase.GREEN_LEAF: 0.8,
        CapsulePhase.YELLOW_LEAF: 0.5,
        CapsulePhase.RED_LEAF: 0.3,
        CapsulePhase.SOIL: 0.0
    }
    
    DECAY_RATES = {
        'P0': 0.0,      # Core knowledge never decays
        'P1': 0.004,   # Important knowledge
        'P2': 0.008    # General knowledge
    }
    
    def __init__(self):
        self.capsules: Dict[str, dict] = {}
    
    def add_capsule(self, capsule_id: str, content: str, 
                   priority: str = 'P2', metadata: Optional[Dict] = None) -> None:
        """Add a new knowledge capsule"""
        self.capsules[capsule_id] = {
            'content': content,
            'confidence': 0.7,  # Start at sprout phase
            'priority': priority,
            'phase': CapsulePhase.SPROUT,
            'created_at': time.time(),
            'last_accessed': time.time(),
            'access_count': 0,
            'metadata': metadata or {}
        }
    
    def access(self, capsule_id: str) -> bool:
        """Access a capsule, boosting its confidence"""
        if capsule_id not in self.capsules:
            return False
        
        capsule = self.capsules[capsule_id]
        capsule['last_accessed'] = time.time()
        capsule['access_count'] += 1
        
        # Boost confidence on access
        boost = 0.03 if capsule['confidence'] < 0.95 else 0.01
        capsule['confidence'] = min(1.0, capsule['confidence'] + boost)
        
        # Update phase
        capsule['phase'] = self._get_phase(capsule['confidence'])
        
        return True
    
    def _get_phase(self, confidence: float) -> CapsulePhase:
        """Determine phase based on confidence"""
        if confidence >= 0.8:
            return CapsulePhase.GREEN_LEAF
        elif confidence >= 0.5:
            return CapsulePhase.YELLOW_LEAF
        elif confidence >= 0.3:
            return CapsulePhase.RED_LEAF
        else:
            return CapsulePhase.SOIL
    
    def decay_all(self) -> None:
        """Apply decay to all capsules based on priority"""
        for capsule in self.capsules.values():
            priority = capsule['priority']
            decay = self.DECAY_RATES.get(priority, 0.008)
            capsule['confidence'] = max(0, capsule['confidence'] - decay)
            capsule['phase'] = self._get_phase(capsule['confidence'])
    
    def get_phase(self, capsule_id: str) -> Optional[str]:
        """Get current phase of a capsule"""
        if capsule_id not in self.capsules:
            return None
        return self.capsules[capsule_id]['phase'].value
    
    def get_status(self) -> Dict:
        """Get overall status of all capsules"""
        phases = {}
        for capsule in self.capsules.values():
            phase = capsule['phase'].value
            phases[phase] = phases.get(phase, 0) + 1
        return phases
    
    def get_capsule(self, capsule_id: str) -> Optional[Dict]:
        """Get capsule details"""
        return self.capsules.get(capsule_id)
    
    def archive(self, capsule_id: str) -> bool:
        """Archive a capsule to soil phase"""
        if capsule_id not in self.capsules:
            return False
        self.capsules[capsule_id]['phase'] = CapsulePhase.SOIL
        self.capsules[capsule_id]['confidence'] = 0.0
        return True
