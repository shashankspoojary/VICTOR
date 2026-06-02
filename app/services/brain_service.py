from enum import Enum
from typing import Dict, Any

class DecisionType(Enum):
    CHAT = "CHAT"
    RESEARCH = "RESEARCH"
    VISION = "VISION"
    TASK = "TASK"
    MEMORY = "MEMORY"
    HYBRID = "HYBRID"

class BrainService:
    def __init__(self):
        self.research_keywords = [
            "latest", "news", "weather", "stock", "today's", "headlines", 
            "recent", "current", "ceo", "research"
        ]
        self.vision_keywords = [
            "image", "screenshot", "describe", "see", "picture", "photo"
        ]
        self.task_keywords = [
            "open", "play", "launch", "search google", "start"
        ]
        self.memory_keywords = [
            "my name", "remember", "recall", "previous", "about me", "memory"
        ]
        self.hybrid_indicators = [
            "and", "then"
        ]

    def classify(self, message: str) -> Dict[str, Any]:
        """
        Classifies the user message into a decision type.
        Returns a dictionary with decision, confidence, and reason.
        """
        msg_lower = message.lower()
        
        scores = {
            DecisionType.RESEARCH: 0,
            DecisionType.VISION: 0,
            DecisionType.TASK: 0,
            DecisionType.MEMORY: 0
        }
        
        if any(kw in msg_lower for kw in self.research_keywords):
            scores[DecisionType.RESEARCH] += 1
            
        if any(kw in msg_lower for kw in self.vision_keywords):
            scores[DecisionType.VISION] += 1
            
        if any(kw in msg_lower for kw in self.task_keywords):
            scores[DecisionType.TASK] += 1
            
        if any(kw in msg_lower for kw in self.memory_keywords):
            scores[DecisionType.MEMORY] += 1
            
        active_capabilities = [cap for cap, score in scores.items() if score > 0]
        has_hybrid_words = any(kw in msg_lower.split() for kw in self.hybrid_indicators)
        
        if len(active_capabilities) > 1 or (len(active_capabilities) == 1 and has_hybrid_words):
            return {
                "decision": DecisionType.HYBRID.value,
                "confidence": 0.85,
                "reason": "Requires multiple capabilities or steps"
            }
            
        if len(active_capabilities) == 1:
            decision = active_capabilities[0]
            reasons = {
                DecisionType.RESEARCH: "Requires internet research",
                DecisionType.VISION: "Requires image analysis",
                DecisionType.TASK: "Requires execution of a task",
                DecisionType.MEMORY: "Requires personal memory access"
            }
            return {
                "decision": decision.value,
                "confidence": 0.90,
                "reason": reasons[decision]
            }
            
        return {
            "decision": DecisionType.CHAT.value,
            "confidence": 0.95,
            "reason": "General conversation"
        }
