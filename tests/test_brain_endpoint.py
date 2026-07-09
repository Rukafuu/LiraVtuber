import pytest
from fastapi.testclient import TestClient
from apps.control_api.server import app


def test_brain_chat_endpoint_validation():
    client = TestClient(app)
    # Test that empty messages are rejected
    response = client.post("/api/brain/chat", json={"message": "", "channel": "terminal"})
    assert response.status_code == 400
    assert "Mensagem do usuario vazia" in response.json()["detail"]
