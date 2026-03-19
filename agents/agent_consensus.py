"""
Consensus Agent — Weighted Voting Across All Agents

Combines predictions from all individual agents into a single consensus signal
based on each agent's historical accuracy. Agents with higher accuracy get
more voting power.

The consensus signal is stored as a separate "Consensus" prediction in the
database, providing investors with a single unified view.
"""

import os
import logging
from database import get_connection

logger = logging.getLogger(__name__)


class ConsensusAgent:
    """
    Produces a consensus signal by weighting individual agent predictions
    by their historical directional accuracy.
    
    If no evaluation data exists, all agents are weighted equally.
    """
    
    name = "Consensus"
    
    def __init__(self):
        self._agent_weights = {}
        self._load_weights()
    
    def _load_weights(self):
        """Load agent accuracy from evaluations table to use as weights."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                is_pg = bool(os.getenv('DATABASE_URL'))
                if is_pg:
                    cursor.execute("""
                        SELECT agent_name,
                               COUNT(*) as total,
                               SUM(CASE WHEN was_correct IS TRUE THEN 1 ELSE 0 END) as correct
                        FROM evaluations
                        WHERE agent_name != %s
                        GROUP BY agent_name
                    """, ('Consensus',))
                else:
                    cursor.execute("""
                        SELECT agent_name,
                               COUNT(*) as total,
                               SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct
                        FROM evaluations
                        WHERE agent_name != ?
                        GROUP BY agent_name
                    """, ('Consensus',))
                
                rows = cursor.fetchall()
                for row in rows:
                    if is_pg:
                        name, total, correct = row['agent_name'], row['total'], row['correct']
                    else:
                        name, total, correct = row[0], row[1], row[2]
                    
                    if total > 0:
                        accuracy = correct / total
                        # Minimum weight of 0.1 to avoid zeroing out any agent
                        self._agent_weights[name] = max(accuracy, 0.1)
                
                if self._agent_weights:
                    logger.info(f"Consensus weights: {self._agent_weights}")
                else:
                    logger.info("No evaluation data yet — equal weights will be used")
                    
        except Exception as e:
            logger.warning(f"Could not load agent weights: {e}")
            self._agent_weights = {}
    
    def predict(self, agent_predictions, sentiment=None):
        """
        Generate consensus signal from individual agent predictions.
        
        Args:
            agent_predictions: dict mapping agent_name -> 'UP'|'DOWN'|'HOLD'
            sentiment: Optional sentiment dict (unused but kept for API consistency)
            
        Returns:
            str: 'UP', 'DOWN', or 'HOLD'
        """
        if not agent_predictions:
            return 'HOLD'
        
        up_weight = 0.0
        down_weight = 0.0
        hold_weight = 0.0
        
        for agent_name, signal in agent_predictions.items():
            if agent_name == self.name:
                continue  # Don't include self
            
            # Get weight (default 0.5 if no history)
            weight = self._agent_weights.get(agent_name, 0.5)
            
            if signal == 'UP':
                up_weight += weight
            elif signal == 'DOWN':
                down_weight += weight
            else:
                hold_weight += weight
        
        total = up_weight + down_weight + hold_weight
        if total == 0:
            return 'HOLD'
        
        # Determine consensus
        if up_weight > down_weight and up_weight > hold_weight:
            return 'UP'
        elif down_weight > up_weight and down_weight > hold_weight:
            return 'DOWN'
        else:
            return 'HOLD'
    
    def get_confidence(self, agent_predictions):
        """
        Calculate confidence as the agreement ratio among agents.
        
        Returns:
            float: 0.0 to 1.0 (1.0 = unanimous)
        """
        if not agent_predictions:
            return 0.0
        
        consensus = self.predict(agent_predictions)
        agreeing = sum(1 for s in agent_predictions.values() 
                       if s == consensus and s != self.name)
        total = len([s for n, s in agent_predictions.items() if n != self.name])
        
        return agreeing / total if total > 0 else 0.0
