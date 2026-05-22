import uuid
import time
import os
from typing import Dict, Any, Optional
import logging

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .langgraph_orchestrator import LangGraphOrchestrator


from .memory import MemoryManager, calculate_significance
from .agents import (
    SchedulingAgent,
    LeaveAgent,
    ComplianceAgent,
    ClarificationAgent,
)
from .audit import AuditLogger

# For backward compatibility with main.py
Orchestrator = LangGraphOrchestrator

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        # Intent keywords for mock fallback
        self.intent_keywords = {
            "scheduling": ["schedule", "meeting", "interview", "appointment"],
            "leave": ["leave", "vacation", "pto", "time off", "holiday"],
            "compliance": ["compliance", "policy", "legal", "regulation", "law"],
        }

        # Sub-agents
        self.agents = {
            "scheduling": SchedulingAgent(),
            "leave": LeaveAgent(),
            "compliance": ComplianceAgent(),
            "clarification": ClarificationAgent(),
        }

        # Memory and audit
        self.memory = MemoryManager()
        self.audit = AuditLogger()

        # LLM setup (Ollama)
        self.use_mock = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
        self.llm = None
        self.classifier_chain = None

        if not self.use_mock:
            try:
                self.llm = ChatOllama(
                    model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                    temperature=0,
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                )
                self.classifier_chain = self._create_classifier_chain()
                logger.info("Ollama LLM initialised successfully")
            except Exception as e:
                logger.warning(f"Failed to initialise Ollama: {e}. Falling back to mock classifier.")
                self.use_mock = True

    def _create_classifier_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in HR automation. Your only job is to classify user requests into one of these intents: 
'scheduling', 'leave', 'compliance'. If the request is unclear, off-topic, or doesn't fit any, return 'clarification'.

Respond with ONLY the intent name, nothing else.

Examples:
User: 'I need to book a meeting room' -> scheduling
User: 'How many vacation days do I have left?' -> leave
User: 'What is the dress code policy?' -> compliance
User: 'What's the weather?' -> clarification
User: 'Hello' -> clarification
"""),
            ("user", "{input}")
        ])
        return prompt | self.llm | StrOutputParser()

    async def route(self, user_id: str, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # 1. Intent classification (LLM or mock)
        intent, confidence = await self._classify_intent(message)

        # 2. Retrieve memory context
        memory_context = await self._retrieve_memory(user_id, intent)

        # 3. Call sub-agent (with retry/timeout)
        agent_response = await self._call_agent(intent, message, memory_context)

        # 4. Store memory based on significance
        significance = calculate_significance(message, intent, confidence)
        await self.memory.store(user_id, f"last_{intent}", {
            "message": message,
            "response": agent_response["text"]
        }, significance)

        # 5. Audit log
        latency = int((time.time() - start_time) * 1000)
        await self.audit.log(
            request_id, user_id, message, intent, confidence,
            agent_response["agent"], agent_response["text"], latency
        )

        return {
            "request_id": request_id,
            "agent_used": agent_response["agent"],
            "response": agent_response["text"],
            "confidence": confidence,
            "memory_context_used": bool(memory_context),
        }

    async def _classify_intent(self, message: str) -> tuple:
        """Classifies intent using Ollama LLM or falls back to keyword matching."""
        if not self.use_mock and self.classifier_chain:
            try:
                intent = await self.classifier_chain.ainvoke({"input": message})
                intent = intent.strip().lower()
                # Validate returned intent
                if intent in ["scheduling", "leave", "compliance", "clarification"]:
                    return intent, 0.92  # LLM confidence is high
                else:
                    logger.warning(f"LLM returned invalid intent '{intent}', falling back")
                    return self._mock_classify_intent(message)
            except Exception as e:
                logger.error(f"LLM classification error: {e}. Using mock fallback.")
                return self._mock_classify_intent(message)
        else:
            return self._mock_classify_intent(message)

    def _mock_classify_intent(self, message: str) -> tuple:
        """Keyword‑based fallback intent classification."""
        msg_lower = message.lower()
        for intent, keywords in self.intent_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                match_count = sum(1 for kw in keywords if kw in msg_lower)
                confidence = min(0.7 + (match_count * 0.1), 0.98)
                return intent, confidence
        return "clarification", 0.45

    async def _retrieve_memory(self, user_id: str, intent: str) -> Dict:
        context_key = f"last_{intent}"
        memory = await self.memory.get(user_id, context_key)
        if memory:
            return {context_key: memory["value"]}
        return {}

    async def _call_agent(self, intent: str, message: str, context: Dict) -> Dict:
        """Call sub-agent with timeout and retry logic."""
        agent = self.agents.get(intent, self.agents["clarification"])
        timeout = agent.get_timeout()
        import asyncio
        try:
            response = await asyncio.wait_for(agent.process(message, context), timeout=timeout)
            return {"agent": intent if intent in self.agents else "clarification", "text": response}
        except asyncio.TimeoutError:
            logger.warning(f"Agent {intent} timed out. Retrying once.")
            try:
                response = await asyncio.wait_for(agent.process(message, context), timeout=timeout)
                return {"agent": intent if intent in self.agents else "clarification", "text": response}
            except Exception as e:
                logger.error(f"Agent {intent} failed after retry: {e}")
        except Exception as e:
            logger.error(f"Agent {intent} error: {e}")

        # Fallback to clarification agent
        fallback = self.agents["clarification"]
        fallback_response = await fallback.process(message, context)
        return {"agent": "clarification", "text": fallback_response}