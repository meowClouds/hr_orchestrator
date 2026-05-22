from .base import BaseAgent
from typing import Dict, Any

class ClarificationAgent(BaseAgent):
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        # Even clarification can use context to avoid repeating itself
        if "last_clarification" in context:
            return "I still need more clarity. Could you rephrase? (Try: scheduling, leave, or compliance)"
        return ("I'm not entirely sure what you need. "
                "Could you rephrase? (e.g., scheduling, leave, or compliance)")

    def get_timeout(self) -> float:
        return 3.0