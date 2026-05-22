from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data

def test_process():
    response = client.post("/process", json={
        "user_id": "bob",
        "message": "I need to schedule a meeting"
    })
    assert response.status_code == 200
    data = response.json()
    assert "agent_used" in data
    assert "response" in data
    assert "confidence" in data
    assert "request_id" in data

def test_audit():
    response = client.get("/audit?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_memory_get():
    response = client.get("/memory/alice")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_memory_delete():
    # First create some memory via a process request
    client.post("/process", json={"user_id": "alice", "message": "urgent leave"})
    # Then delete it
    response = client.delete("/memory/alice/last_leave")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"