from .base import BaseAgent
from typing import Dict, Any

class SchedulingAgent(BaseAgent):
    async def process(self, message: str, context: Dict[str, Any]) -> str:
        return "I've noted your scheduling request. Our calendar team will follow up shortly."

    # Optional: override timeout if needed
    # def get_timeout(self) -> float:
    #     return 3.0