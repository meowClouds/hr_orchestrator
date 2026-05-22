from .base import BaseAgent
from typing import Dict, Any

class ComplianceAgent(BaseAgent):
    """Handles compliance, legal, and policy-related queries."""

    async def process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Mock implementation – in production would query policy database.
        """
        return "For compliance matters, please refer to the employee handbook section 4.2."

    # Optional: override timeout – compliance lookups may be heavier
    def get_timeout(self) -> float:
        return 6.0