from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Abstract base class for all sub-agents."""

    @abstractmethod
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Process a request.

        Args:
            message: User's natural language request.
            context: Dictionary containing retrieved memory.
                     Example: {"last_leave": {"message": "...", "response": "..."}}

        Returns:
            Response string.
        """
        pass

    def get_timeout(self) -> float:
        return 5.0