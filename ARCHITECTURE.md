# JARVIS: Autonomous Developer Operating System

## Architecture Design Document

**Version:** 2.0.0
**Status:** Production Design
**Author:** System Architect

---

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              JARVIS AUTONOMOUS DEV-OS                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           API GATEWAY LAYER                                  │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │   │
│  │  │  REST API    │ │  WebSocket   │ │  gRPC        │ │  VS Code Ext API │   │   │
│  │  │  (FastAPI)   │ │  (Real-time) │ │  (Devices)   │ │  (IDE Bridge)    │   │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          AGENT ORCHESTRATOR                                  │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                         AGENT LOOP ENGINE                             │   │   │
│  │  │   ┌─────────┐   ┌─────────────┐   ┌──────────┐   ┌───────────────┐   │   │   │
│  │  │   │ Planner │──▶│ Tool Select │──▶│ Executor │──▶│ Memory Update │   │   │   │
│  │  │   │  (LLM)  │   │  (Router)   │   │ (Sandbox)│   │   (RAG)       │   │   │   │
│  │  │   └─────────┘   └─────────────┘   └──────────┘   └───────────────┘   │   │   │
│  │  └──────────────────────────────────────────────────────────────────────┘   │   │
│  │  ┌────────────────┐ ┌────────────────┐ ┌──────────────────────────────┐     │   │
│  │  │ Intent Parser  │ │ Plan Generator │ │ Approval Flow Controller     │     │   │
│  │  └────────────────┘ └────────────────┘ └──────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           CORE SERVICES LAYER                                │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐   │   │
│  │  │ Tool       │ │ Memory     │ │ Self-Heal  │ │ Workflow   │ │ Device   │   │   │
│  │  │ Registry   │ │ Service    │ │ Engine     │ │ Engine     │ │ Manager  │   │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐   │   │
│  │  │ Security   │ │ Telemetry  │ │ Event      │ │ Session    │ │ Config   │   │   │
│  │  │ Manager    │ │ Collector  │ │ Bus        │ │ Manager    │ │ Store    │   │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            TOOL LAYER                                        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │ Shell   │ │ File    │ │ Git     │ │ VS Code │ │ Docker  │ │ Process │   │   │
│  │  │ Exec    │ │ Ops     │ │ Ops     │ │ Bridge  │ │ Control │ │ Monitor │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │ HTTP    │ │ DB      │ │ Log     │ │ Network │ │ AI      │ │ Secrets │   │   │
│  │  │ Client  │ │ Client  │ │ Reader  │ │ Scanner │ │ Provider│ │ Manager │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         PERSISTENCE LAYER                                    │   │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐   │   │
│  │  │   PostgreSQL       │  │   Vector Store     │  │   Redis              │   │   │
│  │  │   (Core Data)      │  │   (pgvector)       │  │   (Cache/Queue)      │   │   │
│  │  └────────────────────┘  └────────────────────┘  └──────────────────────┘   │   │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐   │   │
│  │  │   Local Ollama     │  │   File Storage     │  │   SQLite (Offline)   │   │   │
│  │  │   (Embeddings)     │  │   (Artifacts)      │  │   (Fallback)         │   │   │
│  │  └────────────────────┘  └────────────────────┘  └──────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                              EXTERNAL INTEGRATIONS                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Remote  │ │ Cloud   │ │ Ollama  │ │ OpenAI  │ │ GitHub  │ │ SSH Remote      │  │
│  │ Devices │ │ APIs    │ │ Local   │ │ Claude  │ │ APIs    │ │ Agents          │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Folder Structure (Backend-Focused)

```
jarvis/
├── docker/
│   ├── Dockerfile.agent
│   ├── Dockerfile.worker
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
│
├── src/
│   ├── jarvis/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI entrypoint
│   │   ├── config.py                  # Pydantic settings
│   │   │
│   │   ├── api/                       # API Gateway Layer
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py          # Main v1 router
│   │   │   │   ├── agent.py           # /agent endpoints
│   │   │   │   ├── tools.py           # /tools endpoints
│   │   │   │   ├── memory.py          # /memory endpoints
│   │   │   │   ├── workflows.py       # /workflows endpoints
│   │   │   │   ├── devices.py         # /devices endpoints
│   │   │   │   ├── tasks.py           # /tasks endpoints
│   │   │   │   └── system.py          # /system endpoints
│   │   │   ├── websocket/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── manager.py         # Connection manager
│   │   │   │   ├── handlers.py        # Event handlers
│   │   │   │   └── protocol.py        # Message protocol
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py            # API key + JWT
│   │   │   │   ├── rate_limit.py      # Rate limiting
│   │   │   │   ├── logging.py         # Request logging
│   │   │   │   └── error_handler.py   # Global error handler
│   │   │   └── deps.py                # Dependency injection
│   │   │
│   │   ├── agent/                     # Agent Orchestrator
│   │   │   ├── __init__.py
│   │   │   ├── loop.py                # Main agent loop
│   │   │   ├── planner.py             # LLM-based planner
│   │   │   ├── tool_router.py         # Tool selection & routing
│   │   │   ├── executor.py            # Safe execution engine
│   │   │   ├── memory_updater.py      # RAG memory integration
│   │   │   ├── intent/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser.py          # NL intent parsing
│   │   │   │   ├── entities.py        # Entity extraction
│   │   │   │   └── templates.py       # Command templates
│   │   │   ├── approval/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── flow.py            # Approval workflow
│   │   │   │   ├── policies.py        # Approval policies
│   │   │   │   └── notifier.py        # User notification
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── plan.py            # Execution plan models
│   │   │       ├── step.py            # Step definitions
│   │   │       └── result.py          # Execution results
│   │   │
│   │   ├── tools/                     # Tool Layer
│   │   │   ├── __init__.py
│   │   │   ├── registry.py            # Tool registry
│   │   │   ├── base.py                # BaseTool abstract class
│   │   │   ├── schema.py              # JSON schema utilities
│   │   │   ├── sandbox.py             # Sandboxed execution
│   │   │   ├── builtin/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── shell.py           # run_command
│   │   │   │   ├── file.py            # read_file, write_file, list_dir
│   │   │   │   ├── git.py             # git_* operations
│   │   │   │   ├── vscode.py          # vscode_* operations
│   │   │   │   ├── docker.py          # docker_* operations
│   │   │   │   ├── process.py         # process_* operations
│   │   │   │   ├── http.py            # http_request
│   │   │   │   ├── db.py              # db_query (safe subset)
│   │   │   │   ├── log.py             # read_logs, tail_logs
│   │   │   │   ├── network.py         # port_scan, check_endpoint
│   │   │   │   ├── ai.py              # ask_ai, generate_code
│   │   │   │   └── secrets.py         # get_secret (vault integration)
│   │   │   └── plugins/               # User-defined plugins
│   │   │       ├── __init__.py
│   │   │       └── loader.py          # Plugin discovery & loading
│   │   │
│   │   ├── memory/                    # Memory Service (RAG)
│   │   │   ├── __init__.py
│   │   │   ├── service.py             # Memory service facade
│   │   │   ├── short_term.py          # Session memory (Redis)
│   │   │   ├── long_term.py           # Persistent memory (pgvector)
│   │   │   ├── embedder.py            # Ollama embeddings
│   │   │   ├── retriever.py           # Similarity search
│   │   │   ├── indexer.py             # Background indexing
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── memory_item.py     # Memory item schema
│   │   │   │   ├── project_context.py # Project structure
│   │   │   │   └── error_pattern.py   # Error + fix patterns
│   │   │   └── strategies/
│   │   │       ├── __init__.py
│   │   │       ├── recency.py         # Time-based decay
│   │   │       ├── relevance.py       # Semantic relevance
│   │   │       └── importance.py      # Importance scoring
│   │   │
│   │   ├── self_heal/                 # Self-Healing Engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py              # Core self-heal logic
│   │   │   ├── detector.py            # Failure detection
│   │   │   ├── resolver.py            # Auto-resolution strategies
│   │   │   ├── monitors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── process.py         # Process health monitor
│   │   │   │   ├── port.py            # Port conflict detector
│   │   │   │   ├── dependency.py      # Dependency checker
│   │   │   │   ├── disk.py            # Disk space monitor
│   │   │   │   └── service.py         # Service availability
│   │   │   ├── resolvers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── restart.py         # Process restart
│   │   │   │   ├── port_free.py       # Port conflict resolution
│   │   │   │   ├── dep_install.py     # Dependency installation
│   │   │   │   └── cleanup.py         # Resource cleanup
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── issue.py           # Issue definition
│   │   │       └── resolution.py      # Resolution record
│   │   │
│   │   ├── workflow/                  # Workflow Automation Engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py              # Workflow execution
│   │   │   ├── trigger.py             # Trigger system
│   │   │   ├── condition.py           # Conditional logic
│   │   │   ├── action.py              # Action execution
│   │   │   ├── scheduler.py           # Cron-like scheduling
│   │   │   ├── templates/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ci_cd.py           # CI/CD workflow templates
│   │   │   │   ├── deploy.py          # Deployment templates
│   │   │   │   └── maintenance.py     # Maintenance tasks
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── workflow.py        # Workflow definition
│   │   │       ├── trigger.py         # Trigger definition
│   │   │       └── execution.py       # Execution record
│   │   │
│   │   ├── devices/                   # Multi-Device Orchestration
│   │   │   ├── __init__.py
│   │   │   ├── manager.py             # Device manager
│   │   │   ├── registry.py            # Device registry
│   │   │   ├── router.py              # Task routing
│   │   │   ├── adapters/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── local.py           # Local execution
│   │   │   │   ├── ssh.py             # SSH-based remote
│   │   │   │   └── grpc.py            # gRPC-based remote
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── device.py          # Device definition
│   │   │       └── capability.py      # Device capabilities
│   │   │
│   │   ├── security/                  # Security Manager
│   │   │   ├── __init__.py
│   │   │   ├── manager.py             # Security facade
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_key.py         # API key auth
│   │   │   │   ├── jwt.py             # JWT tokens
│   │   │   │   └── device.py          # Device auth
│   │   │   ├── permissions/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── model.py           # Permission model
│   │   │   │   ├── checker.py         # Permission checker
│   │   │   │   └── policies.py        # Security policies
│   │   │   ├── sandbox/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── executor.py        # Sandboxed execution
│   │   │   │   ├── allowlist.py       # Command allowlist
│   │   │   │   └── risk_scorer.py     # Risk assessment
│   │   │   └── audit/
│   │   │       ├── __init__.py
│   │   │       └── logger.py          # Security audit log
│   │   │
│   │   ├── telemetry/                 # Observability
│   │   │   ├── __init__.py
│   │   │   ├── collector.py           # Metrics collection
│   │   │   ├── metrics.py             # Metric definitions
│   │   │   ├── tracer.py              # Distributed tracing
│   │   │   ├── insights.py            # AI-powered insights
│   │   │   └── exporters/
│   │   │       ├── __init__.py
│   │   │       ├── prometheus.py
│   │   │       ├── opentelemetry.py
│   │   │       └── local.py
│   │   │
│   │   ├── llm/                       # LLM Integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py              # LLM client facade
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ollama.py          # Ollama (local)
│   │   │   │   ├── openai.py          # OpenAI API
│   │   │   │   ├── anthropic.py       # Claude API
│   │   │   │   └── azure.py           # Azure OpenAI
│   │   │   ├── prompts/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── planner.py         # Planning prompts
│   │   │   │   ├── tool_select.py     # Tool selection prompts
│   │   │   │   └── intent.py          # Intent parsing prompts
│   │   │   └── function_calling.py    # Function call format
│   │   │
│   │   ├── events/                    # Event Bus
│   │   │   ├── __init__.py
│   │   │   ├── bus.py                 # Event bus
│   │   │   ├── handlers.py            # Event handlers
│   │   │   ├── models.py              # Event models
│   │   │   └── subscribers.py         # Event subscribers
│   │   │
│   │   ├── db/                        # Database Layer
│   │   │   ├── __init__.py
│   │   │   ├── session.py             # SQLAlchemy session
│   │   │   ├── models/                # ORM models
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── user.py
│   │   │   │   ├── device.py
│   │   │   │   ├── memory.py
│   │   │   │   ├── workflow.py
│   │   │   │   ├── task.py
│   │   │   │   └── audit.py
│   │   │   ├── migrations/            # Alembic migrations
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       ├── base.py
│   │   │       ├── memory_repo.py
│   │   │       ├── workflow_repo.py
│   │   │       └── device_repo.py
│   │   │
│   │   └── core/                      # Core Utilities
│   │       ├── __init__.py
│   │       ├── exceptions.py          # Custom exceptions
│   │       ├── logging.py             # Structured logging
│   │       ├── utils.py               # Common utilities
│   │       └── constants.py           # System constants
│   │
│   └── tests/                         # Test Suite
│       ├── __init__.py
│       ├── conftest.py
│       ├── unit/
│       ├── integration/
│       └── e2e/
│
├── vscode-extension/                  # VS Code Extension
│   ├── src/
│   │   ├── extension.ts               # Extension entry
│   │   ├── jarvis-client.ts           # API client
│   │   ├── commands/
│   │   ├── providers/
│   │   └── views/
│   ├── package.json
│   └── tsconfig.json
│
├── migrations/                        # Database Migrations
│   └── versions/
│
├── scripts/
│   ├── setup.sh
│   ├── dev.sh
│   └── deploy.sh
│
├── config/
│   ├── default.yaml
│   ├── production.yaml
│   └── development.yaml
│
├── plugins/                           # Plugin Directory
│   └── example_plugin/
│       ├── __init__.py
│       ├── manifest.yaml
│       └── tools.py
│
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── Makefile
└── README.md
```

---

## 3. Core Services Breakdown

### 3.1 Agent Orchestrator

The brain of the system — coordinates all autonomous operations.

| Component         | Responsibility                                                 |
| ----------------- | -------------------------------------------------------------- |
| **AgentLoop**     | Main execution loop — receives intent, plans, executes, learns |
| **Planner**       | LLM-based reasoning to decompose tasks into steps              |
| **ToolRouter**    | Selects appropriate tool(s) for each step                      |
| **Executor**      | Runs tools in sandboxed environment                            |
| **MemoryUpdater** | Updates RAG memory with outcomes                               |
| **ApprovalFlow**  | Handles user confirmation for risky operations                 |

### 3.2 Tool Registry

Central registry for all available tools (built-in + plugins).

```python
# Tool registration example
@tool_registry.register
class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Execute a shell command"
    risk_level = RiskLevel.MEDIUM

    schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to execute"},
            "cwd": {"type": "string", "description": "Working directory"},
            "timeout": {"type": "integer", "default": 30}
        },
        "required": ["command"]
    }

    async def execute(self, params: dict) -> ToolResult:
        ...
```

### 3.3 Memory Service

Persistent memory using RAG architecture.

| Layer          | Storage               | TTL       | Purpose                               |
| -------------- | --------------------- | --------- | ------------------------------------- |
| **Short-term** | Redis                 | Session   | Current task context, recent commands |
| **Long-term**  | PostgreSQL + pgvector | Permanent | Project knowledge, error patterns     |
| **Embedding**  | Ollama (local)        | N/A       | Text-to-vector conversion             |

### 3.4 Self-Healing Engine

Autonomous issue detection and resolution.

```
Detection → Classification → Resolution Strategy → Execution → Verification
     │              │                  │                │            │
     ▼              ▼                  ▼                ▼            ▼
  Monitors      Classifiers        Resolvers        Sandbox      Health Check
```

### 3.5 Workflow Engine

Event-driven automation system.

```yaml
# Example workflow definition
name: "auto-deploy-on-push"
trigger:
  type: "git_push"
  branch: "main"
conditions:
  - "all_tests_pass"
steps:
  - tool: "run_command"
    params:
      command: "npm run build"
  - tool: "docker_build"
    params:
      tag: "app:${GIT_SHA}"
  - tool: "docker_push"
  - tool: "notify"
    params:
      channel: "deploys"
      message: "Deployed ${GIT_SHA}"
```

### 3.6 Device Manager

Multi-device orchestration layer.

| Device Type    | Connection | Use Case                    |
| -------------- | ---------- | --------------------------- |
| **Local**      | Direct     | Primary development machine |
| **SSH Remote** | SSH tunnel | Remote servers, VMs         |
| **gRPC Agent** | gRPC       | Distributed workers         |

---

## 4. Data Flow Between Components

### 4.1 Request Processing Flow

```
┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌──────────────┐
│  Client  │───▶│ API Gateway│───▶│ Auth Middle │───▶│ Rate Limiter │
└──────────┘    └────────────┘    └─────────────┘    └──────────────┘
                                                              │
                                                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          AGENT ORCHESTRATOR                           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  1. Intent Parser                                               │  │
│  │     "prepare backend for production"                            │  │
│  │        ├── intent: DEPLOYMENT_PREP                              │  │
│  │        └── entities: {target: "backend", env: "production"}     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                    │
│                                  ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  2. Memory Retrieval (RAG)                                      │  │
│  │     - Retrieve past deployment patterns                         │  │
│  │     - Fetch project structure                                   │  │
│  │     - Load developer preferences                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                    │
│                                  ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  3. Planner (LLM)                                               │  │
│  │     Plan:                                                       │  │
│  │     1. Run tests → run_command("npm test")                      │  │
│  │     2. Build project → run_command("npm run build")             │  │
│  │     3. Check deps → check_vulnerabilities()                     │  │
│  │     4. Generate Dockerfile → write_file()                       │  │
│  │     5. Build image → docker_build()                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                    │
│                                  ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  4. Risk Assessment                                             │  │
│  │     - Steps 1-3: LOW risk → auto-approve                        │  │
│  │     - Steps 4-5: MEDIUM risk → request approval                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                    │
│                                  ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  5. Execution Loop                                              │  │
│  │     FOR each step:                                              │  │
│  │       → Select tool from registry                               │  │
│  │       → Execute in sandbox                                      │  │
│  │       → Handle errors (retry / self-heal / abort)               │  │
│  │       → Update memory with result                               │  │
│  │       → Emit events                                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                    │
│                                  ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  6. Response & Learning                                         │  │
│  │     - Return structured result to client                        │  │
│  │     - Store execution pattern in memory                         │  │
│  │     - Update telemetry                                          │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Event Flow

```
┌─────────────┐     ┌───────────────┐     ┌──────────────────┐
│ Git Push    │────▶│   Event Bus   │────▶│ Workflow Trigger │
└─────────────┘     └───────────────┘     └──────────────────┘
                           │                       │
                           │                       ▼
                           │              ┌──────────────────┐
                           │              │ Workflow Engine  │
                           │              └──────────────────┘
                           │                       │
                           ▼                       ▼
                    ┌─────────────┐       ┌──────────────────┐
                    │  WebSocket  │       │  Agent Execute   │
                    │  Broadcast  │       │  (CI/CD Steps)   │
                    └─────────────┘       └──────────────────┘
```

---

## 5. API Design

### 5.1 REST API Endpoints

```yaml
# API Version: v1
# Base URL: /api/v1

# ==================== AGENT ====================
POST   /agent/execute
  description: Execute an intent or command
  body:
    intent: string           # Natural language or structured command
    context?: object         # Additional context
    approval_mode?: string   # "auto" | "confirm" | "dry_run"
  response:
    task_id: string
    status: "queued" | "running" | "completed" | "failed"
    plan?: Plan
    result?: ExecutionResult

GET    /agent/tasks/{task_id}
  description: Get task status and result

POST   /agent/tasks/{task_id}/approve
  description: Approve pending task steps

POST   /agent/tasks/{task_id}/cancel
  description: Cancel running task

# ==================== TOOLS ====================
GET    /tools
  description: List all registered tools
  response:
    tools: Tool[]

GET    /tools/{tool_name}
  description: Get tool details and schema

POST   /tools/{tool_name}/execute
  description: Execute tool directly (bypass agent)
  body:
    params: object
  response:
    result: ToolResult

# ==================== MEMORY ====================
POST   /memory/store
  description: Store memory item
  body:
    type: "context" | "error" | "preference" | "pattern"
    content: string
    metadata?: object

POST   /memory/query
  description: Query memory with semantic search
  body:
    query: string
    limit?: integer
    type_filter?: string[]
  response:
    items: MemoryItem[]

GET    /memory/context/{project_id}
  description: Get project context

DELETE /memory/{memory_id}
  description: Delete memory item

# ==================== WORKFLOWS ====================
GET    /workflows
  description: List all workflows

POST   /workflows
  description: Create new workflow
  body: WorkflowDefinition

GET    /workflows/{workflow_id}
  description: Get workflow details

PUT    /workflows/{workflow_id}
  description: Update workflow

DELETE /workflows/{workflow_id}
  description: Delete workflow

POST   /workflows/{workflow_id}/trigger
  description: Manually trigger workflow

GET    /workflows/{workflow_id}/runs
  description: Get workflow execution history

# ==================== DEVICES ====================
GET    /devices
  description: List registered devices

POST   /devices
  description: Register new device
  body:
    name: string
    type: "local" | "ssh" | "grpc"
    connection: ConnectionConfig
    capabilities: string[]

GET    /devices/{device_id}
  description: Get device details

DELETE /devices/{device_id}
  description: Remove device

POST   /devices/{device_id}/ping
  description: Check device connectivity

# ==================== SYSTEM ====================
GET    /system/health
  description: Health check

GET    /system/info
  description: System information

GET    /system/metrics
  description: Performance metrics

GET    /system/config
  description: Current configuration

POST   /system/self-heal
  description: Trigger self-healing check

GET    /system/logs
  description: Get system logs
  query:
    level?: string
    since?: datetime
    limit?: integer
```

### 5.2 WebSocket Protocol

```typescript
// Connection: ws://host/ws

// Client -> Server Messages
interface ClientMessage {
  type: "subscribe" | "unsubscribe" | "execute" | "approve" | "cancel";
  payload: any;
}

// Server -> Client Messages
interface ServerMessage {
  type:
    | "task_created"
    | "task_progress"
    | "task_completed"
    | "task_failed"
    | "approval_required"
    | "log"
    | "metric"
    | "event";
  payload: any;
  timestamp: string;
}

// Example: Real-time task progress
{
  "type": "task_progress",
  "payload": {
    "task_id": "task_123",
    "step": 2,
    "total_steps": 5,
    "current_tool": "run_command",
    "output": "Running tests...\n✓ 42 tests passed"
  },
  "timestamp": "2026-03-21T10:30:00Z"
}
```

---

## 6. Agent Loop Pseudocode

```python
class AgentLoop:
    """
    Main agent execution loop implementing the OODA pattern:
    Observe → Orient → Decide → Act
    """

    def __init__(
        self,
        planner: Planner,
        tool_registry: ToolRegistry,
        executor: Executor,
        memory: MemoryService,
        approval_flow: ApprovalFlow,
        event_bus: EventBus,
    ):
        self.planner = planner
        self.tool_registry = tool_registry
        self.executor = executor
        self.memory = memory
        self.approval_flow = approval_flow
        self.event_bus = event_bus

    async def execute(
        self,
        intent: str,
        context: dict | None = None,
        approval_mode: ApprovalMode = ApprovalMode.CONFIRM,
    ) -> ExecutionResult:
        """Execute an intent through the agent loop."""

        task = Task.create(intent=intent, context=context)
        self.event_bus.emit(TaskCreated(task))

        try:
            # ═══════════════════════════════════════════════
            # PHASE 1: OBSERVE — Gather context
            # ═══════════════════════════════════════════════

            # Parse intent into structured form
            parsed_intent = await self.planner.parse_intent(intent)

            # Retrieve relevant memories
            memories = await self.memory.query(
                query=intent,
                types=["context", "pattern", "error_fix"],
                limit=10,
            )

            # Get current system state
            system_state = await self._gather_system_state()

            # ═══════════════════════════════════════════════
            # PHASE 2: ORIENT — Understand situation
            # ═══════════════════════════════════════════════

            # Build execution context
            execution_context = ExecutionContext(
                intent=parsed_intent,
                memories=memories,
                system_state=system_state,
                user_context=context,
            )

            # ═══════════════════════════════════════════════
            # PHASE 3: DECIDE — Create plan
            # ═══════════════════════════════════════════════

            plan = await self.planner.create_plan(execution_context)
            task.set_plan(plan)
            self.event_bus.emit(PlanCreated(task, plan))

            # Assess risk for each step
            for step in plan.steps:
                step.risk_level = await self._assess_risk(step)

            # Handle approval based on mode
            if approval_mode == ApprovalMode.DRY_RUN:
                return ExecutionResult(
                    status="dry_run",
                    plan=plan,
                    message="Plan created but not executed",
                )

            if approval_mode == ApprovalMode.CONFIRM:
                high_risk_steps = [s for s in plan.steps if s.risk_level >= RiskLevel.HIGH]
                if high_risk_steps:
                    approval = await self.approval_flow.request_approval(
                        task=task,
                        steps=high_risk_steps,
                    )
                    if not approval.granted:
                        return ExecutionResult(
                            status="cancelled",
                            message="User declined approval",
                        )

            # ═══════════════════════════════════════════════
            # PHASE 4: ACT — Execute plan
            # ═══════════════════════════════════════════════

            results = []

            for step_index, step in enumerate(plan.steps):
                self.event_bus.emit(StepStarted(task, step, step_index))

                try:
                    # Select and validate tool
                    tool = self.tool_registry.get(step.tool_name)
                    if not tool:
                        raise ToolNotFoundError(step.tool_name)

                    # Validate parameters against schema
                    tool.validate_params(step.params)

                    # Execute in sandbox
                    step_result = await self.executor.execute(
                        tool=tool,
                        params=step.params,
                        timeout=step.timeout,
                        sandbox=step.requires_sandbox,
                    )

                    results.append(step_result)
                    self.event_bus.emit(StepCompleted(task, step, step_result))

                    # Update short-term memory with result
                    await self.memory.store_short_term(
                        key=f"task:{task.id}:step:{step_index}",
                        value=step_result,
                    )

                    # Check if step failed
                    if step_result.status == "error":
                        if step.on_error == OnError.ABORT:
                            raise StepExecutionError(step, step_result)
                        elif step.on_error == OnError.RETRY:
                            step_result = await self._retry_step(step, tool, max_attempts=3)
                            if step_result.status == "error":
                                raise StepExecutionError(step, step_result)
                        elif step.on_error == OnError.SELF_HEAL:
                            healed = await self._attempt_self_heal(step, step_result)
                            if not healed:
                                raise StepExecutionError(step, step_result)
                        # OnError.CONTINUE — just continue to next step

                except Exception as e:
                    self.event_bus.emit(StepFailed(task, step, e))

                    # Store error pattern for future learning
                    await self.memory.store_long_term(
                        type="error",
                        content=str(e),
                        metadata={
                            "step": step.dict(),
                            "intent": intent,
                            "context": context,
                        },
                    )

                    raise

            # ═══════════════════════════════════════════════
            # PHASE 5: LEARN — Update memory
            # ═══════════════════════════════════════════════

            # Store successful execution pattern
            await self.memory.store_long_term(
                type="pattern",
                content=f"Successfully executed: {intent}",
                metadata={
                    "intent": intent,
                    "plan": plan.dict(),
                    "results": [r.dict() for r in results],
                },
            )

            execution_result = ExecutionResult(
                status="completed",
                plan=plan,
                results=results,
            )

            self.event_bus.emit(TaskCompleted(task, execution_result))
            return execution_result

        except Exception as e:
            self.event_bus.emit(TaskFailed(task, e))
            return ExecutionResult(
                status="failed",
                error=str(e),
            )

    async def _assess_risk(self, step: PlanStep) -> RiskLevel:
        """Assess risk level of a step."""
        tool = self.tool_registry.get(step.tool_name)
        base_risk = tool.risk_level if tool else RiskLevel.HIGH

        # Elevate risk based on parameters
        if step.tool_name == "run_command":
            cmd = step.params.get("command", "")
            if any(danger in cmd for danger in ["rm ", "del ", "format", "DROP"]):
                return RiskLevel.CRITICAL
            if any(mod in cmd for mod in ["mv ", "cp ", "chmod", "chown"]):
                return max(base_risk, RiskLevel.HIGH)

        return base_risk

    async def _retry_step(
        self,
        step: PlanStep,
        tool: BaseTool,
        max_attempts: int,
    ) -> StepResult:
        """Retry a failed step with exponential backoff."""
        for attempt in range(max_attempts):
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            result = await self.executor.execute(
                tool=tool,
                params=step.params,
                timeout=step.timeout,
            )
            if result.status == "success":
                return result
        return result  # Return last failed result

    async def _attempt_self_heal(
        self,
        step: PlanStep,
        error_result: StepResult,
    ) -> bool:
        """Attempt to self-heal from an error."""
        # Query memory for similar errors and their fixes
        similar_errors = await self.memory.query(
            query=error_result.error,
            types=["error_fix"],
            limit=3,
        )

        for memory in similar_errors:
            fix = memory.metadata.get("fix")
            if fix:
                # Apply the fix
                fix_result = await self.executor.execute(
                    tool=self.tool_registry.get(fix["tool"]),
                    params=fix["params"],
                )
                if fix_result.status == "success":
                    # Retry original step
                    retry_result = await self.executor.execute(
                        tool=self.tool_registry.get(step.tool_name),
                        params=step.params,
                    )
                    if retry_result.status == "success":
                        return True

        return False
```

---

## 7. Tool Interface Schema Examples

### 7.1 Base Tool Schema

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from pydantic import BaseModel

class RiskLevel(Enum):
    LOW = 1       # Read-only, no side effects
    MEDIUM = 2    # Local modifications
    HIGH = 3      # System changes, external calls
    CRITICAL = 4  # Destructive, irreversible

class ToolResult(BaseModel):
    status: str  # "success" | "error"
    output: Any
    error: str | None = None
    metadata: dict = {}

class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str
    description: str
    risk_level: RiskLevel
    requires_approval: bool = False
    timeout: int = 30

    # JSON Schema for parameters
    schema: dict

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def validate_params(self, params: dict) -> None:
        """Validate parameters against schema."""
        # Uses jsonschema to validate
        pass
```

### 7.2 Tool Implementations

```python
# ═══════════════════════════════════════════════════════════════
# run_command — Execute shell commands
# ═══════════════════════════════════════════════════════════════
class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Execute a shell command in the system"
    risk_level = RiskLevel.MEDIUM

    schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute"
            },
            "cwd": {
                "type": "string",
                "description": "Working directory",
                "default": None
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30
            },
            "env": {
                "type": "object",
                "description": "Environment variables",
                "additionalProperties": {"type": "string"}
            }
        },
        "required": ["command"]
    }

    async def execute(self, params: dict) -> ToolResult:
        command = params["command"]
        cwd = params.get("cwd")
        timeout = params.get("timeout", 30)

        # Validate against allowlist
        if not self._is_allowed(command):
            return ToolResult(
                status="error",
                output=None,
                error=f"Command not in allowlist: {command.split()[0]}"
            )

        result = await execute_subprocess(
            command=command,
            cwd=cwd,
            timeout=timeout,
        )

        return ToolResult(
            status="success" if result.returncode == 0 else "error",
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
            metadata={"exit_code": result.returncode}
        )

# ═══════════════════════════════════════════════════════════════
# read_file — Read file contents
# ═══════════════════════════════════════════════════════════════
class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read contents of a file"
    risk_level = RiskLevel.LOW

    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file"
            },
            "encoding": {
                "type": "string",
                "default": "utf-8"
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to read",
                "default": None
            }
        },
        "required": ["path"]
    }

    async def execute(self, params: dict) -> ToolResult:
        path = Path(params["path"]).expanduser().resolve()

        if not path.exists():
            return ToolResult(status="error", output=None, error="File not found")

        if not path.is_file():
            return ToolResult(status="error", output=None, error="Not a file")

        content = path.read_text(encoding=params.get("encoding", "utf-8"))

        if params.get("max_lines"):
            content = "\n".join(content.splitlines()[:params["max_lines"]])

        return ToolResult(
            status="success",
            output=content,
            metadata={"size": path.stat().st_size, "lines": len(content.splitlines())}
        )

# ═══════════════════════════════════════════════════════════════
# write_file — Write contents to file
# ═══════════════════════════════════════════════════════════════
class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write or append content to a file"
    risk_level = RiskLevel.MEDIUM
    requires_approval = True  # Requires approval for new files

    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file"
            },
            "content": {
                "type": "string",
                "description": "Content to write"
            },
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append", "create_only"],
                "default": "overwrite"
            },
            "create_dirs": {
                "type": "boolean",
                "default": False
            }
        },
        "required": ["path", "content"]
    }

    async def execute(self, params: dict) -> ToolResult:
        path = Path(params["path"]).expanduser().resolve()
        mode = params.get("mode", "overwrite")

        if mode == "create_only" and path.exists():
            return ToolResult(status="error", output=None, error="File already exists")

        if params.get("create_dirs"):
            path.parent.mkdir(parents=True, exist_ok=True)

        write_mode = "a" if mode == "append" else "w"
        path.write_text(params["content"], encoding="utf-8")

        return ToolResult(
            status="success",
            output=f"Written {len(params['content'])} bytes to {path}",
            metadata={"path": str(path), "bytes": len(params["content"])}
        )

# ═══════════════════════════════════════════════════════════════
# git_operations — Git commands
# ═══════════════════════════════════════════════════════════════
class GitTool(BaseTool):
    name = "git"
    description = "Execute git operations"
    risk_level = RiskLevel.MEDIUM

    schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "status", "diff", "log", "branch", "checkout",
                    "add", "commit", "push", "pull", "fetch",
                    "stash", "stash_pop", "reset", "merge"
                ]
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "default": []
            },
            "cwd": {
                "type": "string",
                "description": "Repository directory"
            }
        },
        "required": ["operation"]
    }

    SAFE_OPERATIONS = {"status", "diff", "log", "branch", "fetch"}

    async def execute(self, params: dict) -> ToolResult:
        op = params["operation"]
        args = params.get("args", [])

        # Block dangerous reset/force operations
        if op == "reset" and "--hard" in args:
            return ToolResult(
                status="error",
                output=None,
                error="Hard reset requires explicit approval"
            )

        if op == "push" and "--force" in args:
            return ToolResult(
                status="error",
                output=None,
                error="Force push requires explicit approval"
            )

        cmd = f"git {op} {' '.join(args)}"
        # ... execute command
```

### 7.3 Tool Definition JSON (for LLM function calling)

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "run_command",
        "description": "Execute a shell command. Use for running build tools, package managers, scripts.",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {
              "type": "string",
              "description": "The shell command to execute"
            },
            "cwd": {
              "type": "string",
              "description": "Working directory for the command"
            },
            "timeout": {
              "type": "integer",
              "description": "Timeout in seconds (default 30)"
            }
          },
          "required": ["command"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read the contents of a file. Returns the file content as text.",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {
              "type": "string",
              "description": "Absolute or relative path to the file"
            },
            "max_lines": {
              "type": "integer",
              "description": "Maximum number of lines to read"
            }
          },
          "required": ["path"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist.",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {
              "type": "string",
              "description": "Path where to write the file"
            },
            "content": {
              "type": "string",
              "description": "Content to write"
            },
            "mode": {
              "type": "string",
              "enum": ["overwrite", "append", "create_only"],
              "description": "Write mode"
            }
          },
          "required": ["path", "content"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "docker_control",
        "description": "Control Docker containers and images",
        "parameters": {
          "type": "object",
          "properties": {
            "action": {
              "type": "string",
              "enum": [
                "ps",
                "images",
                "build",
                "run",
                "stop",
                "rm",
                "logs",
                "exec"
              ]
            },
            "target": {
              "type": "string",
              "description": "Container name/ID or image name"
            },
            "options": {
              "type": "object",
              "description": "Additional options for the action"
            }
          },
          "required": ["action"]
        }
      }
    }
  ]
}
```

---

## 8. Memory Schema (PostgreSQL + pgvector)

```sql
-- ═══════════════════════════════════════════════════════════════
-- Enable pgvector extension
-- ═══════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════════════
-- Memory Items — Core RAG storage
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE memory_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            VARCHAR(50) NOT NULL,  -- 'context', 'error', 'pattern', 'preference'
    content         TEXT NOT NULL,
    embedding       vector(384),           -- Ollama nomic-embed-text dimension

    -- Metadata
    project_id      VARCHAR(255),
    file_path       VARCHAR(500),
    language        VARCHAR(50),
    tags            TEXT[],

    -- Importance scoring
    importance      FLOAT DEFAULT 0.5,
    access_count    INTEGER DEFAULT 0,
    last_accessed   TIMESTAMPTZ,

    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,           -- NULL = never expires

    -- Soft delete
    deleted_at      TIMESTAMPTZ
);

-- Vector similarity search index (IVFFlat for performance)
CREATE INDEX idx_memory_embedding ON memory_items
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_memory_type ON memory_items(type);
CREATE INDEX idx_memory_project ON memory_items(project_id);
CREATE INDEX idx_memory_created ON memory_items(created_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- Project Context — Cached project structure
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE project_contexts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_path    VARCHAR(500) UNIQUE NOT NULL,
    name            VARCHAR(255),

    -- Detected info
    language        VARCHAR(50),
    framework       VARCHAR(100),
    package_manager VARCHAR(50),

    -- Structure (JSON)
    file_tree       JSONB,
    dependencies    JSONB,
    scripts         JSONB,

    -- Embedding of README + key files
    summary         TEXT,
    summary_embedding vector(384),

    -- When last scanned
    scanned_at      TIMESTAMPTZ DEFAULT NOW(),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Error Patterns — Past errors and their fixes
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE error_patterns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Error identification
    error_type      VARCHAR(100),          -- 'dependency', 'syntax', 'runtime', 'build'
    error_message   TEXT NOT NULL,
    error_embedding vector(384),

    -- Context when error occurred
    context         JSONB,                 -- command, file, project, etc.

    -- Resolution
    fix_description TEXT,
    fix_steps       JSONB,                 -- Array of tool calls that fixed it
    fix_success     BOOLEAN DEFAULT TRUE,

    -- Stats
    occurrence_count INTEGER DEFAULT 1,
    last_occurred   TIMESTAMPTZ DEFAULT NOW(),

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_error_embedding ON error_patterns
    USING ivfflat (error_embedding vector_cosine_ops)
    WITH (lists = 50);

-- ═══════════════════════════════════════════════════════════════
-- Command History — Audit trail of all executed commands
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE command_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was executed
    intent          TEXT,
    tool_name       VARCHAR(100) NOT NULL,
    tool_params     JSONB NOT NULL,

    -- Result
    status          VARCHAR(20) NOT NULL,  -- 'success', 'error', 'timeout'
    output          TEXT,
    error           TEXT,
    exit_code       INTEGER,

    -- Execution context
    device_id       UUID REFERENCES devices(id),
    session_id      UUID,
    task_id         UUID,

    -- Timing
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cmd_history_tool ON command_history(tool_name);
CREATE INDEX idx_cmd_history_status ON command_history(status);
CREATE INDEX idx_cmd_history_created ON command_history(created_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- Developer Preferences
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE preferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(255) DEFAULT 'default',

    key             VARCHAR(100) NOT NULL,
    value           JSONB NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, key)
);

-- ═══════════════════════════════════════════════════════════════
-- Devices — Registered machines
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(50) NOT NULL,  -- 'local', 'ssh', 'grpc'

    -- Connection details (encrypted)
    connection      JSONB NOT NULL,

    -- Capabilities
    capabilities    TEXT[],
    os              VARCHAR(50),
    arch            VARCHAR(50),

    -- Status
    status          VARCHAR(20) DEFAULT 'unknown',
    last_seen       TIMESTAMPTZ,

    -- Auth
    api_key_hash    VARCHAR(64),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Workflows — Automation definitions
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE workflows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,

    -- Definition
    trigger         JSONB NOT NULL,        -- Trigger conditions
    conditions      JSONB,                 -- Pre-conditions
    steps           JSONB NOT NULL,        -- Array of steps

    -- State
    enabled         BOOLEAN DEFAULT TRUE,

    -- Stats
    run_count       INTEGER DEFAULT 0,
    last_run        TIMESTAMPTZ,
    last_status     VARCHAR(20),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Workflow Runs — Execution history
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE workflow_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID REFERENCES workflows(id) ON DELETE CASCADE,

    trigger_event   JSONB,                 -- What triggered this run
    status          VARCHAR(20) NOT NULL,  -- 'running', 'completed', 'failed'

    steps_completed INTEGER DEFAULT 0,
    steps_total     INTEGER,
    current_step    JSONB,

    output          JSONB,
    error           TEXT,

    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════
-- Audit Log — Security events
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    event_type      VARCHAR(50) NOT NULL,
    severity        VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'critical'

    actor           VARCHAR(255),          -- Who did it
    action          VARCHAR(100),          -- What they did
    resource        VARCHAR(255),          -- What was affected

    details         JSONB,
    ip_address      INET,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_type ON audit_log(event_type);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- Helper Functions
-- ═══════════════════════════════════════════════════════════════

-- Semantic search function
CREATE OR REPLACE FUNCTION search_memory(
    query_embedding vector(384),
    match_type VARCHAR DEFAULT NULL,
    match_limit INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    type VARCHAR,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.type,
        m.content,
        1 - (m.embedding <=> query_embedding) AS similarity
    FROM memory_items m
    WHERE m.deleted_at IS NULL
      AND (match_type IS NULL OR m.type = match_type)
      AND m.embedding IS NOT NULL
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql;

-- Update memory access stats
CREATE OR REPLACE FUNCTION update_memory_access()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE memory_items
    SET
        access_count = access_count + 1,
        last_accessed = NOW()
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 9. Security Model

### 9.1 Authentication Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Transport Security                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  • TLS 1.3 for all connections                            │ │
│  │  • Certificate pinning for device-to-device               │ │
│  │  • mTLS for gRPC agents                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Layer 2: Authentication                                        │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  • API Key (X-API-KEY header) — primary method            │ │
│  │  • JWT tokens — for session management                    │ │
│  │  • Device certificates — for remote agents                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Layer 3: Authorization                                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  • Role-based access control (RBAC)                       │ │
│  │  • Tool-level permissions                                 │ │
│  │  • Resource-level access control                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Layer 4: Execution Security                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  • Command allowlisting                                   │ │
│  │  • Parameter sanitization                                 │ │
│  │  • Sandboxed execution                                    │ │
│  │  • Risk assessment + approval flow                        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Permission Model

```python
from enum import Flag, auto

class Permission(Flag):
    """Granular permissions for tools and resources."""

    # Read operations
    READ_FILES = auto()
    READ_LOGS = auto()
    READ_SYSTEM = auto()

    # Write operations
    WRITE_FILES = auto()
    MODIFY_CONFIG = auto()

    # Execution
    EXEC_SAFE = auto()      # npm, python, etc.
    EXEC_SYSTEM = auto()    # System commands
    EXEC_DOCKER = auto()    # Docker operations
    EXEC_GIT = auto()       # Git operations

    # Control
    MANAGE_DEVICES = auto()
    MANAGE_WORKFLOWS = auto()
    MANAGE_MEMORY = auto()

    # Admin
    ADMIN = auto()

# Predefined roles
ROLES = {
    "viewer": Permission.READ_FILES | Permission.READ_LOGS | Permission.READ_SYSTEM,

    "developer": (
        Permission.READ_FILES | Permission.READ_LOGS | Permission.READ_SYSTEM |
        Permission.WRITE_FILES | Permission.EXEC_SAFE | Permission.EXEC_GIT
    ),

    "operator": (
        Permission.READ_FILES | Permission.READ_LOGS | Permission.READ_SYSTEM |
        Permission.EXEC_SAFE | Permission.EXEC_SYSTEM | Permission.EXEC_DOCKER |
        Permission.MANAGE_WORKFLOWS
    ),

    "admin": Permission.ADMIN,  # Full access
}
```

### 9.3 Risk Scoring System

```python
class RiskScorer:
    """Assess risk level of commands and operations."""

    # Command patterns and their base risk
    DANGEROUS_PATTERNS = {
        # Critical — never auto-approve
        r"rm\s+-rf\s+/": RiskLevel.CRITICAL,
        r"mkfs\.": RiskLevel.CRITICAL,
        r"dd\s+if=.+of=/dev/": RiskLevel.CRITICAL,
        r"DROP\s+DATABASE": RiskLevel.CRITICAL,
        r"TRUNCATE\s+TABLE": RiskLevel.CRITICAL,
        r">\s*/etc/": RiskLevel.CRITICAL,

        # High risk
        r"rm\s+-rf": RiskLevel.HIGH,
        r"chmod\s+777": RiskLevel.HIGH,
        r"curl\s+.+\|\s*(bash|sh)": RiskLevel.HIGH,
        r"--force": RiskLevel.HIGH,
        r"--hard": RiskLevel.HIGH,
        r"sudo\s+": RiskLevel.HIGH,

        # Medium risk
        r"npm\s+install(?!\s+--save)": RiskLevel.MEDIUM,
        r"pip\s+install": RiskLevel.MEDIUM,
        r"docker\s+run": RiskLevel.MEDIUM,
        r"git\s+push": RiskLevel.MEDIUM,
        r"git\s+reset": RiskLevel.MEDIUM,
    }

    # File paths that are sensitive
    SENSITIVE_PATHS = {
        RiskLevel.CRITICAL: ["/etc/passwd", "/etc/shadow", "~/.ssh/"],
        RiskLevel.HIGH: [".env", "credentials", "secrets", ".git/config"],
        RiskLevel.MEDIUM: ["package.json", "requirements.txt", "Dockerfile"],
    }

    def score(self, tool: str, params: dict) -> RiskScore:
        """Calculate risk score for a tool invocation."""
        base_risk = self._get_tool_base_risk(tool)

        # Check for dangerous patterns
        if tool == "run_command":
            command = params.get("command", "")
            pattern_risk = self._check_patterns(command)
            base_risk = max(base_risk, pattern_risk)

        # Check for sensitive paths
        if tool in ["read_file", "write_file"]:
            path = params.get("path", "")
            path_risk = self._check_path_sensitivity(path)
            base_risk = max(base_risk, path_risk)

        return RiskScore(
            level=base_risk,
            requires_approval=base_risk >= RiskLevel.HIGH,
            reason=self._explain_risk(base_risk),
        )
```

### 9.4 Sandboxed Execution

```python
class SandboxExecutor:
    """Execute commands in isolated environment."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.allowlist = CommandAllowlist(config.allowlist_path)

    async def execute(
        self,
        command: str,
        *,
        cwd: Path | None = None,
        env: dict | None = None,
        timeout: int = 30,
        user: str | None = None,
    ) -> ExecutionResult:
        """Execute command with security constraints."""

        # 1. Validate against allowlist
        if not self.allowlist.is_allowed(command):
            raise SecurityError(f"Command not in allowlist: {command}")

        # 2. Sanitize parameters
        command = self._sanitize_command(command)
        env = self._sanitize_env(env or {})

        # 3. Restrict working directory
        if cwd:
            cwd = self._validate_cwd(cwd)

        # 4. Set resource limits (Linux: cgroups, Windows: Job objects)
        limits = ResourceLimits(
            max_memory_mb=self.config.max_memory_mb,
            max_cpu_percent=self.config.max_cpu_percent,
            max_file_descriptors=self.config.max_fds,
            network_access=self.config.allow_network,
        )

        # 5. Execute with timeout
        try:
            result = await asyncio.wait_for(
                self._run_isolated(command, cwd, env, limits, user),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise ExecutionTimeout(f"Command timed out after {timeout}s")

    def _sanitize_command(self, command: str) -> str:
        """Remove dangerous patterns from command."""
        # Remove shell injections
        dangerous = [";", "&&", "||", "|", "`", "$(", "${"]
        for pattern in dangerous:
            if pattern in command and not self._is_safe_usage(command, pattern):
                raise SecurityError(f"Potentially dangerous pattern: {pattern}")
        return command
```

---

## 10. Deployment Strategy

### 10.1 Docker Compose (Development)

```yaml
# docker-compose.yml
version: "3.9"

services:
  jarvis-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.agent
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://jarvis:jarvis@postgres:5432/jarvis
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_HOST=http://ollama:11434
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src:/app/src:ro
      - jarvis-data:/data
    depends_on:
      - postgres
      - redis
      - ollama
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: jarvis
      POSTGRES_DB: jarvis
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jarvis"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  postgres-data:
  redis-data:
  ollama-data:
  jarvis-data:
```

### 10.2 Local Development (Windows)

```powershell
# setup.ps1 — Windows local setup script

# 1. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Setup local PostgreSQL (via Docker)
docker run -d --name jarvis-postgres `
    -e POSTGRES_USER=jarvis `
    -e POSTGRES_PASSWORD=jarvis `
    -e POSTGRES_DB=jarvis `
    -p 5432:5432 `
    pgvector/pgvector:pg16

# 4. Setup local Redis (via Docker)
docker run -d --name jarvis-redis -p 6379:6379 redis:7-alpine

# 5. Setup Ollama (native or Docker)
# Native: Download from https://ollama.ai/download
# Pull required models
ollama pull nomic-embed-text   # For embeddings
ollama pull llama3.2           # For reasoning

# 6. Initialize database
alembic upgrade head

# 7. Start development server
uvicorn jarvis.main:app --reload --host 0.0.0.0 --port 8000
```

### 10.3 Production Deployment

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  jarvis-api:
    image: ${REGISTRY}/jarvis:${TAG:-latest}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "2"
          memory: 4G
      restart_policy:
        condition: on-failure
        max_attempts: 3
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OLLAMA_HOST=${OLLAMA_HOST}
      - API_KEY=${API_KEY}
      - LOG_LEVEL=INFO
      - ENVIRONMENT=production
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.jarvis.rule=Host(`jarvis.example.com`)"
      - "traefik.http.routers.jarvis.tls=true"
      - "traefik.http.routers.jarvis.tls.certresolver=letsencrypt"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  jarvis-worker:
    image: ${REGISTRY}/jarvis-worker:${TAG:-latest}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1"
          memory: 2G
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - WORKER_CONCURRENCY=4
    command: ["celery", "-A", "jarvis.worker", "worker", "--loglevel=info"]

  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "letsencrypt:/letsencrypt"

volumes:
  letsencrypt:
```

### 10.4 Hybrid Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID DEPLOYMENT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CLOUD LAYER                           │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ API Gateway  │  │ Auth Service │  │ Memory Store │  │   │
│  │  │ (Optional)   │  │ (JWT/OAuth)  │  │ (pgvector)   │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  │                           │                              │   │
│  │  Use for: Multi-device sync, remote access, backups     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                         ┌────┴────┐                             │
│                         │  HTTPS  │                             │
│                         └────┬────┘                             │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    LOCAL LAYER (Primary)                 │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ JARVIS Core  │  │ Ollama       │  │ Local SQLite │  │   │
│  │  │ (FastAPI)    │  │ (LLM/Embed)  │  │ (Offline)    │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  │         │                                                │   │
│  │         │         ┌──────────────┐  ┌──────────────┐    │   │
│  │         ├────────▶│ VS Code Ext  │  │ Docker       │    │   │
│  │         │         └──────────────┘  └──────────────┘    │   │
│  │         │                                                │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │              EXECUTION SANDBOX                    │   │   │
│  │  │   [Shell] [Git] [Docker] [Process] [Network]     │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │  Runs on: Windows laptop (primary dev machine)          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                         ┌────┴────┐                             │
│                         │ SSH/gRPC│                             │
│                         └────┬────┘                             │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    REMOTE AGENTS                         │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ Dev Server 1 │  │ Dev Server 2 │  │ CI Runner    │  │   │
│  │  │ (SSH Agent)  │  │ (gRPC Agent) │  │ (gRPC Agent) │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  │                                                          │   │
│  │  For: Remote builds, testing, deployment                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Implementation Phases

### Phase 1: Core Agent + Tools (Weeks 1-3)

**Deliverables:**

- [ ] Agent loop implementation
- [ ] Tool registry system
- [ ] 8 core tools (shell, file r/w, git, vscode, docker, process, log, system)
- [ ] Basic LLM integration (Ollama)
- [ ] REST API endpoints
- [ ] API key authentication

**Dependencies:**

- FastAPI, Pydantic, asyncio
- Ollama installed locally

**Risks:**

- LLM response quality for planning
- Windows subprocess handling edge cases

**Mitigation:**

- Use structured prompts with examples
- Extensive testing on Windows

---

### Phase 2: Memory + RAG (Weeks 4-5)

**Deliverables:**

- [ ] PostgreSQL + pgvector setup
- [ ] Embedding service (Ollama nomic-embed-text)
- [ ] Short-term memory (Redis)
- [ ] Long-term memory with semantic search
- [ ] Project context indexing
- [ ] Error pattern storage

**Dependencies:**

- Phase 1 complete
- PostgreSQL with pgvector
- Redis

**Risks:**

- Embedding model latency
- Vector search accuracy

**Mitigation:**

- Batch embeddings, cache common queries
- Tune similarity thresholds, add metadata filtering

---

### Phase 3: Self-Healing (Weeks 6-7)

**Deliverables:**

- [ ] Health monitors (process, port, dependency, disk)
- [ ] Issue detection system
- [ ] Auto-resolvers
- [ ] Approval flow for repairs
- [ ] Audit logging

**Dependencies:**

- Phase 2 complete (memory for pattern matching)

**Risks:**

- False positive detections
- Unsafe auto-remediation

**Mitigation:**

- Conservative thresholds, require approval for system changes
- Extensive testing in isolated environment

---

### Phase 4: Multi-Device Orchestration (Weeks 8-9)

**Deliverables:**

- [ ] Device registry
- [ ] Local execution adapter
- [ ] SSH adapter
- [ ] gRPC adapter
- [ ] Task routing system
- [ ] Device health monitoring

**Dependencies:**

- Phase 1 complete

**Risks:**

- Network latency
- SSH connection stability
- Cross-platform command differences

**Mitigation:**

- Async execution with timeouts
- Connection pooling, auto-reconnect
- Device capability detection

---

### Phase 5: Workflow Engine (Weeks 10-11)

**Deliverables:**

- [ ] Workflow definition schema
- [ ] Trigger system (event, schedule, webhook)
- [ ] Condition evaluator
- [ ] Step executor
- [ ] Workflow UI-ready API
- [ ] Template library (CI/CD, deploy, maintenance)

**Dependencies:**

- Phase 1 + Phase 2

**Risks:**

- Complex workflow state management
- Trigger reliability

**Mitigation:**

- Use state machine pattern
- Persistent queue for triggers (Redis streams)

---

### Phase 6: IDE Integration (Weeks 12-14)

**Deliverables:**

- [ ] VS Code extension scaffold
- [ ] Extension ↔ Backend communication
- [ ] Active file/context capture
- [ ] Code modification capabilities
- [ ] Inline suggestions
- [ ] Command palette integration

**Dependencies:**

- Phase 1 API stable

**Risks:**

- VS Code API changes
- Extension performance impact

**Mitigation:**

- Use VS Code stable APIs only
- Lazy loading, minimal background work

---

### Phase 7: Observability + Intelligence (Weeks 15-16)

**Deliverables:**

- [ ] Metrics collection (Prometheus format)
- [ ] Distributed tracing
- [ ] Performance dashboards
- [ ] AI-powered insights
- [ ] Usage analytics
- [ ] Optimization recommendations

**Dependencies:**

- All previous phases

**Risks:**

- Metric cardinality explosion
- Insight accuracy

**Mitigation:**

- Careful metric design, sampling for high-cardinality
- Ground insights with historical data validation

---

## 12. Summary

This architecture transforms JARVIS from a remote control tool into a **fully autonomous developer operating system** while maintaining:

1. **Modularity** — Clear separation between API, Agent, Tools, Memory, and Services
2. **Security** — Multi-layer auth, sandboxed execution, risk scoring, approval flows
3. **Extensibility** — Plugin system for tools, configurable LLM providers
4. **Offline-first** — Works fully local with Ollama, optional cloud sync
5. **Production-ready** — Docker deployment, observability, self-healing

The phased approach ensures incremental delivery with clear milestones while managing dependencies and risks at each stage.
