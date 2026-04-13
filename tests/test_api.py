"""
Tests for API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestAPIImports:
    """Test API module imports."""

    def test_import_main(self):
        from jarvis.main import app
        assert app is not None

    def test_import_router(self):
        from jarvis.api.v1.router import router
        assert router is not None

    def test_import_endpoints(self):
        from jarvis.api.v1 import (
            agent,
            tools,
            system,
            memory,
            self_heal,
            devices,
            workflows,
            ide,
            observability,
        )
        assert agent is not None
        assert tools is not None
        assert system is not None


class TestAPIEndpoints:
    """Test API endpoint responses."""

    @pytest.fixture
    def client(self):
        from jarvis.main import app
        return TestClient(app)

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data or "status" in data

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_system_info(self, client):
        response = client.get("/api/v1/system/info")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data or "name" in data

    def test_list_tools(self, client):
        response = client.get("/api/v1/tools")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_self_heal_health(self, client):
        response = client.get("/api/v1/self-heal/health")
        assert response.status_code == 200

    def test_devices_list(self, client):
        response = client.get("/api/v1/devices")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_workflows_list(self, client):
        response = client.get("/api/v1/workflows")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_ide_adapters(self, client):
        response = client.get("/api/v1/ide/adapters")
        assert response.status_code == 200

    def test_observability_metrics(self, client):
        response = client.get("/api/v1/observability/metrics")
        assert response.status_code == 200

    def test_observability_prometheus(self, client):
        response = client.get("/api/v1/observability/prometheus")
        assert response.status_code == 200
        # Should be text/plain content
        assert "text" in response.headers.get("content-type", "")


class TestChatEndpoint:
    """Tests for the conversational chat and code-review endpoints."""

    @pytest.fixture
    def client(self):
        from jarvis.main import app
        return TestClient(app)

    def test_chat_no_llm_returns_error_message(self, client):
        """Chat endpoint returns a 200 with an error field when no LLM is configured."""
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "Hello JARVIS", "history": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        # Without a real LLM configured the endpoint still returns a session_id
        assert isinstance(data["session_id"], str)

    def test_chat_assigns_session_id(self, client):
        """Each chat call returns a stable session_id."""
        r1 = client.post("/api/v1/agent/chat", json={"message": "hi", "history": []})
        assert r1.status_code == 200
        sid = r1.json()["session_id"]

        # Use the same session_id for the next turn
        r2 = client.post(
            "/api/v1/agent/chat",
            json={"message": "hello again", "history": [], "session_id": sid},
        )
        assert r2.status_code == 200
        assert r2.json()["session_id"] == sid

    def test_review_no_llm_returns_error(self, client):
        """Code review returns a 200 response even when LLM is unavailable."""
        response = client.post(
            "/api/v1/agent/review",
            json={"code": "def foo(): pass", "language": "python"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "issues" in data
        assert "score" in data

    def test_workflow_generate_no_llm_returns_503(self, client):
        """Workflow generation returns 503 when no LLM is available."""
        response = client.post(
            "/api/v1/workflows/generate",
            json={"description": "run tests then deploy"},
        )
        assert response.status_code == 503
