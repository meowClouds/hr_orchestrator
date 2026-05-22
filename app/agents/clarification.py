from .base import BaseAgent
from typing import Dict, Any

class ClarificationAgent(BaseAgent):
    """Fallback agent for low-confidence requests or unrecognised intents."""

    async def process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Asks the user to rephrase or provides examples of supported requests.
        """
        return ("I'm not entirely sure what you need. "
                "Could you rephrase? (e.g., scheduling, leave, or compliance)")

    # Optional: override timeout – simple response, fast timeout
    def get_timeout(self) -> float:
        return 3.0