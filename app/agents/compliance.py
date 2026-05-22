from .base import BaseAgent
from typing import Dict, Any

class ComplianceAgent(BaseAgent):
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        if "last_compliance" in context:
            prev = context["last_compliance"]
            return (f"You previously asked about compliance: '{prev['message']}'. "
                    f"Now: '{message}'. Please refer to handbook section 4.2 for detailed policies.")
        return "For compliance matters, please refer to the employee handbook section 4.2."

    def get_timeout(self) -> float:
        return 6.0