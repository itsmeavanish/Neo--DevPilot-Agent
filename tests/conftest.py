"""
Pytest configuration and fixtures for JARVIS tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from pathlib import Path

# Configure asyncio for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_workflow_file(tmp_path: Path) -> Path:
    """Create a temporary workflow file for testing."""
    workflow_content = """
name: test-workflow
description: A test workflow
version: "1.0"

steps:
  - id: step1
    name: First Step
    type: tool
    tool: shell_execute
    params:
      command: echo "Hello"
  - id: step2
    name: Second Step
    type: tool
    tool: shell_execute
    params:
      command: echo "World"
    depends_on:
      - step1
"""
    workflow_file = tmp_path / "test_workflow.yaml"
    workflow_file.write_text(workflow_content)
    return workflow_file


@pytest.fixture
def sample_device_data() -> dict:
    """Sample device data for testing."""
    return {
        "id": "test-device-001",
        "name": "Test Device",
        "device_type": "desktop",
        "role": "worker",
        "host": "localhost",
        "port": 8080,
        "capabilities": {
            "tools": ["shell_execute", "file_read"],
            "max_concurrent_tasks": 4,
            "gpu_available": False,
            "memory_mb": 8192,
            "cpu_cores": 4,
        },
    }


@pytest.fixture
def sample_issue_data() -> dict:
    """Sample issue data for self-healing tests."""
    return {
        "id": "issue-001",
        "type": "port_conflict",
        "severity": "high",
        "source": "port_monitor",
        "description": "Port 3000 is already in use",
        "context": {
            "port": 3000,
            "pid": 12345,
            "process_name": "node",
        },
    }
