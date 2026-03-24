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
