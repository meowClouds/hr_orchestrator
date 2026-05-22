# HR Automation Platform – Multi-Agent Orchestrator

A production‑ready HR automation system that routes natural language requests to specialised sub‑agents using a LangGraph orchestration engine. Built with FastAPI, Ollama (local LLM), and a two‑tier memory system (STM/LTM).

## Features

- 6 REST endpoints (including a new root `/` info endpoint)
- Intent classification with confidence scores (LLM + keyword fallback)
- Sub‑agents: Scheduling, Leave, Compliance, Clarification (now use injected memory context)
- Two‑tier memory (STM in‑memory TTL, LTM SQLite)
- Significance scoring logic (confidence + urgency + intent type)
- Append‑only audit log (SQLite with triggers)
- Retry & timeout logic for agent calls
- LangGraph conditional branching: low‑confidence requests → direct to ClarificationAgent
- Graceful fallback for errors (no raw stack traces)
- Modular design with clear separation of concerns

## Tech Stack

| Component          | Technology                         |
|--------------------|------------------------------------|
| Language           | Python 3.11+                       |
| Web Framework      | FastAPI + Uvicorn                  |
| Orchestration      | LangGraph (StateGraph)             |
| LLM Integration    | LangChain + Ollama (local)         |
| Databases          | SQLite (audit + LTM)               |
| Testing            | pytest + FastAPI TestClient        |
| Environment        | python‑dotenv                      |

## Prerequisites

- **Python 3.11 or 3.12** (3.13 may work but 3.12 recommended)
- **Ollama** installed and running – [Download](https://ollama.com)
- **Git** (optional)

## Installation

### 1. Clone / extract the project
```bash
cd hr_orchestrator
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
#### if any langchain langgraph installation conflicts arise use: 
```bash
pip install --upgrade langchain-ollama langchain-core langgraph
```

### 4. Pull a local LLM model (for Ollama)
```bash
ollama pull llama3.2:3b
```

### 5. Configure environment variables
Copy the example configuration:
```bash
cp .env.example .env
```
Edit `.env` (minimal example):
```env
USE_MOCK_LLM=false
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
STM_TTL_SECONDS=300
LTM_DB_PATH=long_term_memory.db
AUDIT_DB_PATH=audit.db
```
> Set `USE_MOCK_LLM=true` to run without Ollama (uses keyword‑only fallback).

### 6. Run the server
```bash
uvicorn app.main:app --reload
```
Open `http://localhost:8000/docs` to explore the interactive API documentation.

## API Endpoints

| Method | Endpoint                         | Description                          |
|--------|----------------------------------|--------------------------------------|
| GET    | `/`                              | API information and endpoint list    |
| POST   | `/process`                       | Send a natural language request      |
| GET    | `/audit`                         | Retrieve audit log (limit, user_id)  |
| GET    | `/memory/{user_id}`              | Get user memory (both STM and LTM)   |
| DELETE | `/memory/{user_id}/{key}`        | Delete a specific memory entry       |
| GET    | `/health`                        | Health check (DB, orchestrator)      |

### Example Request – `/process`
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "message": "I need urgent leave"}'
```
**Response:**
```json
{
  "request_id": "abc-123",
  "agent_used": "leave",
  "response": "Your leave request has been logged. Current balance: 12 days.",
  "confidence": 0.92,
  "memory_context_used": false
}
```

### Example Request – `/audit`
```bash
curl "http://localhost:8000/audit?limit=10&user_id=alice"
```

## Project Structure
```
hr_orchestrator/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── orchestrator.py            # LangGraph wrapper (exposes Orchestrator)
│   ├── langgraph_orchestrator.py  # StateGraph with confidence branching
│   ├── llm_classifier.py          # Ollama + mock fallback
│   ├── audit.py                   # Append‑only SQLite audit log
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── manager.py             # STM/LTM implementation
│   │   └── significance.py        # Significance scoring logic
│   └── agents/
│       ├── __init__.py
│       ├── base.py                # BaseAgent (abstract)
│       ├── scheduling.py          # Uses context memory
│       ├── leave.py               # Uses context memory
│       ├── compliance.py          # Uses context memory
│       └── clarification.py       # Uses context memory
├── tests/
│   └── test_orchestrator.py       # pytest suite
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

## Testing

Run the test suite with:
```bash
  pytest tests/ -v
```
All tests use FastAPI’s `TestClient` (synchronous, no extra plugins needed).

## How It Works

### LangGraph Orchestration with Confidence‑Based Branching
1. **User request** → FastAPI (`/process`)
2. **Orchestrator (LangGraph)** invokes nodes:
   - `classify_intent` → LLM (or keyword fallback) returns intent + confidence
   - **Conditional branch:** if confidence < 0.6 → go directly to `clarify`
   - If high confidence: `retrieve_memory` → `call_agent` → `store_memory` → `log_audit`
   - If low confidence: `clarify` → `store_memory` → `log_audit`
3. **Response** returned to user.

### Significance Scoring
`significance = (confidence × 0.6) + urgency_bonus (0.2) + intent_bonus (0.1‑0.2)`
- **Confidence** (0–1) – from LLM or keyword matching
- **Urgency** – keywords like “urgent”, “asap”, “emergency”
- **Intent** – compliance (+0.2), scheduling/leave (+0.1), clarification (0)

Threshold **0.7** promotes a memory to LTM (persistent); below that stays in STM (expires after TTL).

### Context Injection in Sub‑Agents
Agents receive a `context` dictionary containing previous memories (e.g., `{"last_leave": {"message": "...", "response": "..."}}`). They use this to personalise responses.

Example from `LeaveAgent`:
``` python
if "last_leave" in context:
    prev = context["last_leave"]
    return f"Previous request: '{prev['message']}'. Now: '{message}'. Balance: 12 days."
```

### Append‑Only Audit Log
The `audit_log` table in `audit.db` is protected by SQLite triggers that raise an error on `UPDATE` or `DELETE`. All entries contain:
- timestamp, request_id, user_id, message, intent, confidence, agent_used, response, latency_ms

## Troubleshooting

| Issue                          | Solution                                                       |
|--------------------------------|----------------------------------------------------------------|
| **Ollama connection refused**  | Run `ollama serve` in a separate terminal                     |
| **`ImportError: is_data_content_block`** | Upgrade packages: `pip install --upgrade langchain-core langchain-ollama` |
| **Port 8000 already in use**   | Change port: `uvicorn app.main:app --port 8001`               |
| **Module not found**           | Activate virtual environment and run `pip install -r requirements.txt` |
| **SQLite “database is locked”**| Ensure only one process writes at a time (aiosqlite handles this) |

## Trade‑Offs & Honest Reflection

- **Local LLM (Ollama) vs OpenAI** – free, private, but slower; fallback classifier ensures functionality.
- **Significance threshold (0.7)** – arbitrary but justified by need to keep only highly relevant interactions in LTM.
- **Sub‑agent stubs** – do not call real APIs, but they now use injected context to personalise responses.
- **LangGraph** – adds complexity, but demonstrates state‑machine with conditional branching.
- **Root endpoint** – added to provide API info and avoid 404 on base URL.

## Future Improvements

- Add LangGraph checkpointing for workflow persistence
- Replace sub‑agent stubs with real API integrations (calendar, HRIS, policy database)
- Implement streaming responses for long‑running agents
- Add structured logging with request ID propagation

## License

Educational use only – HR Automation Assignment.

## Acknowledgments

Built with FastAPI, LangGraph, Ollama, and SQLite. Inspired by modern agentic RAG patterns.