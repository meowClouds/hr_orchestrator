from .base import BaseAgent
from typing import Dict, Any

class LeaveAgent(BaseAgent):
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        if "last_leave" in context:
            prev = context["last_leave"]
            return (f"Your previous leave request was about '{prev['message']}'. "
                    f"Now you're asking: '{message}'. I've logged this request. "
                    "Current balance: 12 days.")
        return "Your leave request has been logged. Current balance: 12 days."

    def get_timeout(self) -> float:
        return 4.0