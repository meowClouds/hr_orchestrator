from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Abstract base class for all sub-agents."""

    @abstractmethod
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Process a request relevant to this agent.

        Args:
            message: User's natural language request.
            context: Memory context (e.g., previous interactions, user data).

        Returns:
            Response string to send back to the user.
        """
        pass

    def get_timeout(self) -> float:
        """Return timeout in seconds for this agent. Can be overridden."""
        return 5.0  # default timeout