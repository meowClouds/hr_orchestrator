from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

# --- Enums for restricted values ---
class AgentType(str, Enum):
    """Enum for allowed agent types."""
    SCHEDULING = "scheduling"
    LEAVE = "leave"
    COMPLIANCE = "compliance"
    CLARIFICATION = "clarification"

class MemoryType(str, Enum):
    """Enum for memory tier types."""
    STM = "STM"
    LTM = "LTM"

# --- Request/Response Models for API Endpoints ---

class ProcessRequest(BaseModel):
    """Model for the request body to the /process endpoint."""
    user_id: str = Field(..., description="The ID of the user making the request")
    message: str = Field(..., description="The natural language request from the user")
    session_id: Optional[str] = Field(None, description="An optional session ID for grouping requests")

    @validator('user_id', 'message')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v

class ProcessResponse(BaseModel):
    """Model for the response body from the /process endpoint."""
    request_id: str
    agent_used: str
    response: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    memory_context_used: bool

class AuditEntry(BaseModel):
    """Model for a single entry in the audit log."""
    id: int
    timestamp: datetime
    request_id: str
    user_id: str
    message: str
    intent: str
    confidence: float
    agent_used: str
    response: str
    latency_ms: int

class MemoryEntry(BaseModel):
    """Model for a memory entry (both STM and LTM)."""
    key: str
    value: Any
    significance: float
    type: MemoryType

# --- Internal Orchestrator Models ---

class IntentResult(BaseModel):
    """Model for the result from the intent classifier."""
    intent: AgentType
    confidence: float
    raw_response: Optional[str] = None

class AgentResponse(BaseModel):
    """Standardized response from a sub-agent."""
    agent: AgentType
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- Database / Internal Models for Memory Management ---

class MemoryItem(BaseModel):
    """Internal model for a memory item stored in STM or LTM."""
    user_id: str
    key: str
    value: Any
    significance: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: Optional[int] = None

class LTMModel(MemoryItem):
    """Model for an LTM entry stored in SQLite."""
    pass

class STMModel(MemoryItem):
    """Model for an STM entry stored in memory."""
    pass

class HealthResponse(BaseModel):
    """Model for the health check endpoint response."""
    status: str
    database: str
    orchestrator: str