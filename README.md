# JARVIS - Autonomous Developer Operating System

**Version 2.0.0**

JARVIS is a production-grade AI-powered development assistant that acts as an autonomous operating system for developers. It combines intelligent task automation, self-healing capabilities, multi-device orchestration, and comprehensive observability into a unified platform.

## Features

### Core Agent Infrastructure

- **Intent Classification**: Automatically understands and categorizes user requests
- **Action Planning**: ReAct pattern-based planning for complex tasks
- **Tool Registry**: Dynamic tool discovery and management
- **LLM Integration**: Supports multiple LLM providers (Ollama, etc.)

### RAG Memory System

- **Short-term Memory**: Fast in-memory storage for session context
- **Long-term Memory**: Vector-based storage using ChromaDB
- **Contextual Retrieval**: Intelligent memory search with embeddings
- **Memory Persistence**: Durable storage across sessions

### Self-Healing System

- **Health Monitors**:
  - Port conflict detection
  - Disk space monitoring
  - Memory usage tracking
  - Process/service health checks
  - Dependency verification

- **Auto-Resolvers**:
  - Port conflict resolution (process termination)
  - Disk cleanup (temp files, caches, logs)
  - Service restart automation
  - Dependency installation

- **Approval Flow**: Configurable approval for destructive operations

### Multi-Device Orchestration

- **Device Registry**: Automatic local device detection
- **WebSocket Protocol**: Real-time device communication
- **Load Balancing Strategies**:
  - Round-robin
  - Least-loaded
  - Capability-match
  - Local-preferred
- **Task Distribution**: Intelligent task routing based on device capabilities

### Workflow Engine

- **Workflow Definitions**: YAML/JSON workflow files
- **Step Types**:
  - `tool`: Execute registered tools
  - `intent`: Natural language commands
  - `condition`: Conditional branching
  - `parallel`: Concurrent execution
  - `loop`: Iterative steps
  - `approval`: Human-in-the-loop
  - `notify`: Notifications
  - `script`: Inline scripts

- **Triggers**:
  - Manual execution
  - Schedule (cron expressions)
  - File watch (directory monitoring)
  - Webhook endpoints
  - Git events

- **Variable Interpolation**: `${var}`, `${steps.id.result}`, `${env.VAR}`

### IDE Integration

- **Supported IDEs**:
  - VS Code
  - Cursor

- **Features**:
  - Diagnostics parsing (errors, warnings)
  - Code navigation
  - File editing
  - Terminal integration
  - Command execution

### Observability

- **Metrics**:
  - Counter (monotonic)
  - Gauge (variable values)
  - Histogram (distributions)
  - Prometheus-compatible export

- **Distributed Tracing**:
  - Span-based tracing
  - Trace context propagation
  - Automatic function instrumentation

- **Dashboard**:
  - System statistics
  - Component health
  - Activity summaries

## Installation

### Prerequisites

- Python 3.11+
- pip or pipx

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/jarvis.git
cd jarvis

# Install dependencies
pip install -e ".[dev]"

# Run the server
jarvis
```

### Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/

# Type checking
mypy src/
```

## Configuration

Create a `.env` file in the project root:

```env
# Server Configuration
JARVIS_HOST=0.0.0.0
JARVIS_PORT=8000
JARVIS_DEBUG=false

# LLM Configuration
JARVIS_LLM_PROVIDER=ollama
JARVIS_LLM_MODEL=llama3.2
JARVIS_LLM_BASE_URL=http://localhost:11434

# Memory Configuration
JARVIS_MEMORY_TYPE=chroma
JARVIS_MEMORY_PATH=./data/memory

# Self-Healing
JARVIS_SELF_HEAL_ENABLED=true
JARVIS_SELF_HEAL_AUTO_RESOLVE=false
```

## API Reference

### Base URL

```
http://localhost:8000/api/v1
```

### Endpoints

#### Agent

| Method | Endpoint         | Description                 |
| ------ | ---------------- | --------------------------- |
| POST   | `/agent/chat`    | Send a message to the agent |
| POST   | `/agent/execute` | Execute a specific tool     |
| GET    | `/agent/history` | Get conversation history    |

#### Tools

| Method | Endpoint                | Description              |
| ------ | ----------------------- | ------------------------ |
| GET    | `/tools`                | List all available tools |
| GET    | `/tools/{name}`         | Get tool details         |
| POST   | `/tools/{name}/execute` | Execute a tool           |

#### System

| Method | Endpoint         | Description            |
| ------ | ---------------- | ---------------------- |
| GET    | `/system/info`   | Get system information |
| GET    | `/system/status` | Get system status      |

#### Memory

| Method | Endpoint         | Description          |
| ------ | ---------------- | -------------------- |
| POST   | `/memory/store`  | Store a memory item  |
| POST   | `/memory/search` | Search memory        |
| DELETE | `/memory/{id}`   | Delete a memory item |

#### Self-Healing

| Method | Endpoint                  | Description              |
| ------ | ------------------------- | ------------------------ |
| GET    | `/self-heal/health`       | Get health check results |
| GET    | `/self-heal/issues`       | List detected issues     |
| POST   | `/self-heal/resolve/{id}` | Resolve an issue         |

#### Devices

| Method | Endpoint             | Description           |
| ------ | -------------------- | --------------------- |
| GET    | `/devices`           | List all devices      |
| GET    | `/devices/{id}`      | Get device details    |
| POST   | `/devices/{id}/task` | Assign task to device |
| WS     | `/devices/ws`        | WebSocket connection  |

#### Workflows

| Method | Endpoint                 | Description         |
| ------ | ------------------------ | ------------------- |
| GET    | `/workflows`             | List all workflows  |
| POST   | `/workflows`             | Create a workflow   |
| POST   | `/workflows/{id}/run`    | Run a workflow      |
| GET    | `/workflows/{id}/status` | Get workflow status |

#### IDE

| Method | Endpoint           | Description       |
| ------ | ------------------ | ----------------- |
| GET    | `/ide/adapters`    | List IDE adapters |
| POST   | `/ide/open`        | Open file in IDE  |
| GET    | `/ide/diagnostics` | Get diagnostics   |
| POST   | `/ide/edit`        | Apply edits       |

#### Observability

| Method | Endpoint                    | Description        |
| ------ | --------------------------- | ------------------ |
| GET    | `/observability/metrics`    | Get all metrics    |
| GET    | `/observability/prometheus` | Prometheus format  |
| GET    | `/observability/traces`     | Get recent traces  |
| GET    | `/observability/dashboard`  | Get dashboard data |

## Usage Examples

### Chat with Agent

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/agent/chat",
    json={"message": "Create a new Python project with FastAPI"}
)
print(response.json())
```

### Execute a Tool

```python
response = httpx.post(
    "http://localhost:8000/api/v1/tools/shell_execute/execute",
    json={"command": "echo 'Hello, JARVIS!'"}
)
print(response.json())
```

### Create a Workflow

```yaml
# workflow.yaml
name: build-and-test
description: Build and test the project
version: "1.0"

triggers:
  - type: file_watch
    path: ./src
    patterns: ["*.py"]

steps:
  - id: lint
    name: Run Linter
    type: tool
    tool: shell_execute
    params:
      command: ruff check src/

  - id: test
    name: Run Tests
    type: tool
    tool: shell_execute
    params:
      command: pytest tests/ -v
    depends_on:
      - lint

  - id: notify
    name: Notify Success
    type: notify
    message: "Build completed successfully!"
    depends_on:
      - test
```

### Monitor Health

```python
response = httpx.get("http://localhost:8000/api/v1/self-heal/health")
health = response.json()
for check in health["checks"]:
    print(f"{check['name']}: {check['status']}")
```

## Architecture

```
jarvis/
├── src/jarvis/
│   ├── agent/          # Agent loop, planner, executor
│   ├── api/            # FastAPI endpoints
│   │   └── v1/         # API version 1
│   ├── core/           # Core utilities, logging, exceptions
│   ├── devices/        # Multi-device orchestration
│   ├── ide/            # IDE integration adapters
│   ├── llm/            # LLM client and providers
│   ├── memory/         # RAG memory system
│   ├── observability/  # Metrics, tracing, dashboard
│   ├── self_heal/      # Self-healing monitors and resolvers
│   ├── tools/          # Tool registry and builtins
│   └── workflows/      # Workflow engine
├── tests/              # Test suite
└── pyproject.toml      # Project configuration
```

## Built-in Tools

| Tool            | Description            |
| --------------- | ---------------------- |
| `file_read`     | Read file contents     |
| `file_write`    | Write to files         |
| `file_delete`   | Delete files           |
| `shell_execute` | Execute shell commands |
| `git_status`    | Get git status         |
| `git_commit`    | Create git commits     |
| `git_push`      | Push to remote         |
| `docker_ps`     | List containers        |
| `docker_build`  | Build images           |
| `system_info`   | Get system information |
| `process_list`  | List running processes |
| `log_tail`      | Tail log files         |

## Contributing
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/your-org/jarvis/issues)
- Documentation: [Full documentation](https://jarvis-docs.example.com)

---

**JARVIS** - Your Autonomous Developer Operating System
