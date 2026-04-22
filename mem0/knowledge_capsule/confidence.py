"""
Confidence Tracker with Bayesian Updates
Integrates prior knowledge with new evidence
"""

from typing import Dict, Optional, List, Tuple
import math
from collections import defaultdict

class ConfidenceTracker:
    """
    Tracks confidence in knowledge using Bayesian inference.
    Integrates prior beliefs with new evidence.
    """
    
    def __init__(self):
        self.beliefs: Dict[str, dict] = {}
    
    def set_prior(self, hypothesis: str, prior: float, metadata: Optional[Dict] = None) -> None:
        """
        Set prior belief for a hypothesis.
        
        Args:
            hypothesis: The hypothesis or knowledge claim
            prior: Initial probability (0.0 to 1.0)
            metadata: Additional context
        """
        self.beliefs[hypothesis] = {
            'prior': prior,
            'posterior': prior,
            'likelihoods': [],
            'evidence_count': 0,
            'metadata': metadata or {}
        }
    
    def update(self, hypothesis: str, likelihood: float, 
              evidence: Optional[str] = None) -> float:
        """
        Update belief using Bayesian inference.
        
        P(H|E) = P(E|H) * P(H) / P(E)
        
        Args:
            hypothesis: The hypothesis being updated
            likelihood: P(E|H) - probability of evidence given hypothesis
            evidence: Optional description of the evidence
            
        Returns:
            Updated posterior probability
        """
        if hypothesis not in self.beliefs:
            self.set_prior(hypothesis, 0.5)
        
        belief = self.beliefs[hypothesis]
        prior = belief['posterior']
        
        # Bayesian update
        numerator = likelihood * prior
        denominator = likelihood * prior + (1 - likelihood) * (1 - prior)
        
        if denominator > 0:
            posterior = numerator / denominator
        else:
            posterior = prior
        
        # Store update
        belief['posterior'] = posterior
        belief['likelihoods'].append({
            'likelihood': likelihood,
            'evidence': evidence,
            'result': posterior
        })
        belief['evidence_count'] += 1
        
        return posterior
    
    def get_confidence(self, hypothesis: str) -> float:
        """Get current confidence level for a hypothesis"""
        if hypothesis not in self.beliefs:
            return 0.5
        return self.beliefs[hypothesis]['posterior']
    
    def get_belief_state(self, hypothesis: str) -> Optional[Dict]:
        """Get full belief state"""
        return self.beliefs.get(hypothesis)
    
    def get_all_beliefs(self) -> Dict[str, float]:
        """Get all current beliefs"""
        return {
            h: b['posterior'] 
            for h, b in self.beliefs.items()
        }
    
    def get_high_confidence(self, threshold: float = 0.8) -> List[Tuple[str, float]]:
        """Get hypotheses above confidence threshold"""
        return [
            (h, b['posterior']) 
            for h, b in self.beliefs.items() 
            if b['posterior'] >= threshold
        ]
    
    def get_uncertain(self, threshold: float = 0.4) -> List[Tuple[str, float]]:
        """Get hypotheses below confidence threshold (need more evidence)"""
        return [
            (h, b['posterior']) 
            for h, b in self.beliefs.items() 
            if b['posterior'] < threshold
        ]
