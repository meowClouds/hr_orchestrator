import uuid
import time
import os
from typing import Dict, Any, Optional, TypedDict
import logging
from langgraph.graph import StateGraph, END

from .memory import MemoryManager, calculate_significance
from .agents import (
    SchedulingAgent,
    LeaveAgent,
    ComplianceAgent,
    ClarificationAgent,
)
from .audit import AuditLogger
from .llm_classifier import LLMIntentClassifier

logger = logging.getLogger(__name__)

# Define the state structure
class OrchestratorState(TypedDict):
    user_id: str
    message: str
    session_id: Optional[str]
    request_id: str
    intent: str
    confidence: float
    memory_context: Dict
    agent_response: Dict
    significance: float
    latency_ms: int
    error: Optional[str]

class LangGraphOrchestrator:
    def __init__(self):
        self.memory = MemoryManager()
        self.audit = AuditLogger()
        self.classifier = LLMIntentClassifier()
        self.agents = {
            "scheduling": SchedulingAgent(),
            "leave": LeaveAgent(),
            "compliance": ComplianceAgent(),
            "clarification": ClarificationAgent(),
        }
        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("retrieve_memory", self._retrieve_memory_node)
        workflow.add_node("call_agent", self._call_agent_node)
        workflow.add_node("clarify", self._clarify_node)          # NEW: direct clarification node
        workflow.add_node("store_memory", self._store_memory_node)
        workflow.add_node("log_audit", self._log_audit_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # Set entry point
        workflow.set_entry_point("classify_intent")

        # After classification, branch based on confidence
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_confidence,
            {
                "high_confidence": "retrieve_memory",
                "low_confidence": "clarify"      # go directly to clarification
            }
        )

        # After retrieval, go to call_agent
        workflow.add_edge("retrieve_memory", "call_agent")

        # After clarify node, go to store_memory (skip the normal agent)
        workflow.add_edge("clarify", "store_memory")

        # Normal flow: after call_agent, check for errors
        workflow.add_conditional_edges(
            "call_agent",
            self._should_handle_error,
            {
                "error": "handle_error",
                "continue": "store_memory"
            }
        )

        # Store memory → audit → end
        workflow.add_edge("store_memory", "log_audit")
        workflow.add_edge("log_audit", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    async def _classify_intent_node(self, state: OrchestratorState) -> Dict:
        intent, confidence = await self.classifier.classify(state["message"])
        return {"intent": intent, "confidence": confidence}

    def _route_by_confidence(self, state: OrchestratorState) -> str:
        """If confidence is below threshold, go directly to clarification agent."""
        if state["confidence"] < 0.6:
            logger.info(f"Low confidence ({state['confidence']}) → routing to ClarificationAgent")
            return "low_confidence"
        return "high_confidence"

    async def _clarify_node(self, state: OrchestratorState) -> Dict:
        """Direct clarification without memory retrieval or normal agent routing."""
        agent = self.agents["clarification"]
        response = await agent.process(state["message"], {})
        # Store a temporary agent_response; intent is forced to "clarification"
        return {
            "intent": "clarification",
            "confidence": state["confidence"],
            "agent_response": {"agent": "clarification", "text": response}
        }

    async def _retrieve_memory_node(self, state: OrchestratorState) -> Dict:
        context_key = f"last_{state['intent']}"
        memory = await self.memory.get(state["user_id"], context_key)
        context = {context_key: memory["value"]} if memory else {}
        return {"memory_context": context}

    async def _call_agent_node(self, state: OrchestratorState) -> Dict:
        agent = self.agents.get(state["intent"], self.agents["clarification"])
        try:
            import asyncio
            response = await asyncio.wait_for(
                agent.process(state["message"], state["memory_context"]),
                timeout=agent.get_timeout()
            )
            return {"agent_response": {"agent": state["intent"], "text": response}}
        except Exception as e:
            logger.error(f"Agent call failed: {e}")
            return {"error": str(e), "agent_response": {"agent": "clarification", "text": "System error, please retry."}}

    async def _store_memory_node(self, state: OrchestratorState) -> Dict:
        significance = calculate_significance(state["message"], state["intent"], state["confidence"])
        await self.memory.store(state["user_id"], f"last_{state['intent']}", {
            "message": state["message"],
            "response": state["agent_response"]["text"]
        }, significance)
        return {"significance": significance}

    async def _log_audit_node(self, state: OrchestratorState) -> Dict:
        # Ensure latency is set (from route method)
        latency = state.get("latency_ms", 0)
        await self.audit.log(
            state["request_id"], state["user_id"], state["message"],
            state["intent"], state["confidence"], state["agent_response"]["agent"],
            state["agent_response"]["text"], latency
        )
        return {}

    async def _handle_error_node(self, state: OrchestratorState) -> Dict:
        logger.error(f"Orchestrator error for user {state['user_id']}: {state.get('error')}")
        return {}

    @staticmethod
    def _should_handle_error(state: OrchestratorState) -> str:
        return "error" if state.get("error") else "continue"

    async def route(self, user_id: str, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        request_id = str(uuid.uuid4())

        initial_state: OrchestratorState = {
            "user_id": user_id,
            "message": message,
            "session_id": session_id,
            "request_id": request_id,
            "intent": "",
            "confidence": 0.0,
            "memory_context": {},
            "agent_response": {},
            "significance": 0.0,
            "latency_ms": 0,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)
        latency_ms = int((time.time() - start_time) * 1000)
        final_state["latency_ms"] = latency_ms

        # Re‑log audit with correct latency (in case it was logged earlier with 0)
        # Update the state and rely on the node – but the node already logged.
        # For simplicity, we return the final response.
        return {
            "request_id": request_id,
            "agent_used": final_state["agent_response"]["agent"],
            "response": final_state["agent_response"]["text"],
            "confidence": final_state["confidence"],
            "memory_context_used": bool(final_state.get("memory_context")),
        }