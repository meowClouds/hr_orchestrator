import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
from dotenv import load_dotenv

load_dotenv()

from .orchestrator import Orchestrator
from .audit import AuditLogger
from .memory import MemoryManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="HR Automation Platform", version="1.0.0")

# Initialize core components
orchestrator = Orchestrator()
audit_logger = AuditLogger()
memory_manager = MemoryManager()

# Request/Response Models
class UserRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

class ProcessResponse(BaseModel):
    request_id: str
    agent_used: str
    response: str
    confidence: float
    memory_context_used: bool

class AuditEntry(BaseModel):
    timestamp: str
    request_id: str
    user_id: str
    message: str
    intent: str
    confidence: float
    agent_used: str
    response: str
    latency_ms: int

class MemoryEntry(BaseModel):
    key: str
    value: Any
    significance: float
    type: str  # "STM" or "LTM"

# ---------------------------
# 5 Required REST Endpoints
# ---------------------------

@app.post("/process", response_model=ProcessResponse)
async def process_request(request: UserRequest):
    """
    Endpoint 1: Handle natural language request.
    Routes to appropriate sub-agent via orchestrator.
    """
    try:
        # Orchestrator handles: intent classification, memory retrieval, agent routing
        result = await orchestrator.route(request.user_id, request.message, request.session_id)
        return ProcessResponse(**result)
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error")

@app.get("/audit", response_model=List[AuditEntry])
async def get_audit_log(limit: int = 100, user_id: Optional[str] = None):
    """
    Endpoint 2: Retrieve recent audit log entries.
    Optional filter by user_id.
    """
    try:
        entries = await audit_logger.get_entries(limit=limit, user_id=user_id)
        return entries
    except Exception as e:
        logger.error(f"Audit retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not retrieve audit log")

@app.get("/memory/{user_id}", response_model=List[MemoryEntry])
async def get_user_memory(user_id: str, memory_type: Optional[str] = None):
    """
    Endpoint 3: Retrieve STM and/or LTM for a user.
    memory_type = "STM", "LTM", or None for both.
    """
    try:
        memories = await memory_manager.get_all(user_id, memory_type)
        return memories
    except Exception as e:
        logger.error(f"Memory retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not retrieve memory")

@app.delete("/memory/{user_id}/{key}")
async def delete_memory_entry(user_id: str, key: str):
    """
    Endpoint 4: Delete a specific memory entry (e.g., for testing or GDPR).
    """
    try:
        success = await memory_manager.delete_entry(user_id, key)
        if not success:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"status": "deleted", "key": key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory deletion failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not delete memory")

@app.get("/health")
async def health_check():
    """
    Endpoint 5: Health monitoring.
    """
    # Could check DB connectivity, LLM availability, etc.
    db_ok = await audit_logger.ping()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "orchestrator": "ready"
    }

@app.get("/")
async def root():
    return {
        "name": "HR Automation Platform",
        "version": "1.0.0",
        "description": "Multi-agent task routing with memory and audit",
        "endpoints": [
            {"path": "/process", "method": "POST", "description": "Submit a request"},
            {"path": "/audit", "method": "GET", "description": "Get audit logs"},
            {"path": "/memory/{user_id}", "method": "GET", "description": "Get user memory"},
            {"path": "/memory/{user_id}/{key}", "method": "DELETE", "description": "Delete memory entry"},
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/docs", "method": "GET", "description": "Swagger UI"}
        ]
    }