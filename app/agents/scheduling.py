from .base import BaseAgent
from typing import Dict, Any

class SchedulingAgent(BaseAgent):
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        # If there is previous scheduling context, mention it
        if "last_scheduling" in context:
            prev = context["last_scheduling"]
            return (f"I see you previously asked about scheduling: '{prev['message']}'. "
                    f"I've noted your new request: '{message}'. Our calendar team will follow up.")
        return "I've noted your scheduling request. Our calendar team will follow up shortly."

    def get_timeout(self) -> float:
        return 3.0