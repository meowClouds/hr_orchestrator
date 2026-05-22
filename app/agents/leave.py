from .base import BaseAgent
from typing import Dict, Any

class LeaveAgent(BaseAgent):
    """Handles leave requests, balance checks, and time-off queries."""

    async def process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Mock implementation – in production would call HR system / leave API.
        """
        return "Your leave request has been logged. Current balance: 12 days."

    # Optional: override timeout – leave APIs might be slower
    def get_timeout(self) -> float:
        return 4.0