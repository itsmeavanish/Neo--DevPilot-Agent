# JARVIS Feature List

## Complete Feature & Function Reference

This document provides a comprehensive list of all features and functions added during the JARVIS transformation to an Autonomous Developer Operating System.

---

## Phase 1: Core Agent Infrastructure

### Agent Loop (`src/jarvis/agent/loop.py`)

| Function                            | Description                                  |
| ----------------------------------- | -------------------------------------------- |
| `AgentLoop.run()`                   | Main agent execution loop with ReAct pattern |
| `AgentLoop.process_intent()`        | Classify and process user intents            |
| `AgentLoop.execute_plan()`          | Execute action plans                         |
| `AgentLoop.execute_distributed()`   | Distribute tasks across devices              |
| `AgentLoop.execute_parallel()`      | Execute multiple tasks in parallel           |
| `AgentLoop.get_available_devices()` | Get list of available devices                |

### Planner (`src/jarvis/agent/planner.py`)

| Function              | Description                    |
| --------------------- | ------------------------------ |
| `Planner.plan()`      | Create action plan from intent |
| `Planner.decompose()` | Break complex tasks into steps |

### Executor (`src/jarvis/agent/executor.py`)

| Function                  | Description               |
| ------------------------- | ------------------------- |
| `Executor.execute()`      | Execute a single action   |
| `Executor.execute_tool()` | Execute a registered tool |

### Tool Registry (`src/jarvis/tools/registry.py`)

| Function                    | Description               |
| --------------------------- | ------------------------- |
| `ToolRegistry.register()`   | Register a new tool       |
| `ToolRegistry.get()`        | Get tool by name          |
| `ToolRegistry.list_tools()` | List all registered tools |
| `ToolRegistry.execute()`    | Execute a tool by name    |

---

## Phase 2: RAG Memory System

### Short-term Memory (`src/jarvis/memory/short_term.py`)

| Function                   | Description          |
| -------------------------- | -------------------- |
| `ShortTermMemory.store()`  | Store item in memory |
| `ShortTermMemory.get()`    | Retrieve item by ID  |
| `ShortTermMemory.search()` | Search recent items  |
| `ShortTermMemory.clear()`  | Clear all items      |

### Long-term Memory (`src/jarvis/memory/long_term.py`)

| Function                       | Description           |
| ------------------------------ | --------------------- |
| `LongTermMemory.store()`       | Store with embeddings |
| `LongTermMemory.search()`      | Semantic search       |
| `LongTermMemory.delete()`      | Delete item           |
| `LongTermMemory.get_similar()` | Find similar items    |

### Embedder (`src/jarvis/memory/embedder.py`)

| Function                 | Description         |
| ------------------------ | ------------------- |
| `Embedder.embed()`       | Generate embeddings |
| `Embedder.embed_batch()` | Batch embedding     |

### Memory Service (`src/jarvis/memory/service.py`)

| Function                      | Description          |
| ----------------------------- | -------------------- |
| `MemoryService.store()`       | Unified storage      |
| `MemoryService.search()`      | Unified search       |
| `MemoryService.get_context()` | Get relevant context |

---

## Phase 3: Self-Healing System

### Monitors

#### Port Monitor (`src/jarvis/self_heal/monitors/port.py`)

| Function                       | Description              |
| ------------------------------ | ------------------------ |
| `PortMonitor.check()`          | Check for port conflicts |
| `PortMonitor.get_port_usage()` | Get port usage info      |

#### Disk Monitor (`src/jarvis/self_heal/monitors/disk.py`)

| Function                  | Description          |
| ------------------------- | -------------------- |
| `DiskMonitor.check()`     | Check disk space     |
| `DiskMonitor.get_usage()` | Get disk usage stats |

#### Process Monitor (`src/jarvis/self_heal/monitors/process.py`)

| Function                         | Description              |
| -------------------------------- | ------------------------ |
| `ProcessMonitor.check()`         | Check process health     |
| `ProcessMonitor.get_processes()` | List monitored processes |

#### Dependency Monitor (`src/jarvis/self_heal/monitors/dependency.py`)

| Function                             | Description                 |
| ------------------------------------ | --------------------------- |
| `DependencyMonitor.check()`          | Check dependencies          |
| `DependencyMonitor.verify_package()` | Verify package installation |

### Resolvers

#### Port Free Resolver (`src/jarvis/self_heal/resolvers/port_free.py`)

| Function                        | Description               |
| ------------------------------- | ------------------------- |
| `PortFreeResolver.resolve()`    | Free up conflicting ports |
| `PortFreeResolver.can_handle()` | Check if can handle issue |

#### Cleanup Resolver (`src/jarvis/self_heal/resolvers/cleanup.py`)

| Function                        | Description         |
| ------------------------------- | ------------------- |
| `CleanupResolver.resolve()`     | Clean up disk space |
| `CleanupResolver.clean_temp()`  | Clean temp files    |
| `CleanupResolver.clean_cache()` | Clean cache files   |
| `CleanupResolver.clean_logs()`  | Clean old logs      |

#### Restart Resolver (`src/jarvis/self_heal/resolvers/restart.py`)

| Function                       | Description             |
| ------------------------------ | ----------------------- |
| `RestartResolver.resolve()`    | Restart failed services |
| `RestartResolver.can_handle()` | Check if can handle     |

#### Dependency Installer (`src/jarvis/self_heal/resolvers/dep_install.py`)

| Function                               | Description                  |
| -------------------------------------- | ---------------------------- |
| `DepInstallResolver.resolve()`         | Install missing dependencies |
| `DepInstallResolver.install_package()` | Install a package            |

### Self-Heal Engine (`src/jarvis/self_heal/engine.py`)

| Function                            | Description                 |
| ----------------------------------- | --------------------------- |
| `SelfHealEngine.check_health()`     | Run all health checks       |
| `SelfHealEngine.get_issues()`       | Get detected issues         |
| `SelfHealEngine.resolve()`          | Resolve an issue            |
| `SelfHealEngine.auto_resolve()`     | Auto-resolve safe issues    |
| `SelfHealEngine.start_monitoring()` | Start background monitoring |
| `SelfHealEngine.stop_monitoring()`  | Stop monitoring             |

---

## Phase 4: Multi-Device Orchestration

### Device Models (`src/jarvis/devices/models/device.py`)

| Class                | Description                                                  |
| -------------------- | ------------------------------------------------------------ |
| `DeviceType`         | Enum: DESKTOP, LAPTOP, SERVER, MOBILE, CONTAINER, VM, REMOTE |
| `DeviceRole`         | Enum: COORDINATOR, WORKER, HYBRID                            |
| `DeviceStatus`       | Enum: ONLINE, OFFLINE, BUSY, ERROR                           |
| `DeviceCapabilities` | Dataclass for device capabilities                            |
| `DeviceMetrics`      | Dataclass for device metrics                                 |
| `Device`             | Main device dataclass                                        |
| `DeviceTask`         | Task assignment dataclass                                    |

### Device Registry (`src/jarvis/devices/registry.py`)

| Function                                  | Description                 |
| ----------------------------------------- | --------------------------- |
| `DeviceRegistry.register()`               | Register a device           |
| `DeviceRegistry.unregister()`             | Remove a device             |
| `DeviceRegistry.get()`                    | Get device by ID            |
| `DeviceRegistry.get_all()`                | Get all devices             |
| `DeviceRegistry.get_online()`             | Get online devices          |
| `DeviceRegistry.get_available()`          | Get available devices       |
| `DeviceRegistry.select_for_tool()`        | Select best device for tool |
| `DeviceRegistry.select_by_capabilities()` | Select by requirements      |
| `DeviceRegistry.update_heartbeat()`       | Update device heartbeat     |
| `DeviceRegistry.update_metrics()`         | Update device metrics       |
| `DeviceRegistry.check_stale_devices()`    | Check for stale devices     |
| `DeviceRegistry.queue_task()`             | Queue task for device       |
| `DeviceRegistry.complete_task()`          | Mark task complete          |

### Device Protocol (`src/jarvis/devices/protocol.py`)

| Class/Function                        | Description                                            |
| ------------------------------------- | ------------------------------------------------------ |
| `MessageType`                         | Enum: HELLO, HEARTBEAT, TASK_ASSIGN, TASK_RESULT, etc. |
| `DeviceMessage`                       | Message dataclass                                      |
| `DeviceProtocol.encode()`             | Encode message                                         |
| `DeviceProtocol.decode()`             | Decode message                                         |
| `DeviceProtocol.create_hello()`       | Create hello message                                   |
| `DeviceProtocol.create_heartbeat()`   | Create heartbeat                                       |
| `DeviceProtocol.create_task_assign()` | Create task assignment                                 |

### Task Distributor (`src/jarvis/devices/distributor.py`)

| Function                             | Description                                                                |
| ------------------------------------ | -------------------------------------------------------------------------- |
| `LoadBalanceStrategy`                | Enum: ROUND_ROBIN, LEAST_LOADED, CAPABILITY_MATCH, LOCAL_PREFERRED, RANDOM |
| `TaskDistributor.select_device()`    | Select device for task                                                     |
| `TaskDistributor.distribute()`       | Distribute task                                                            |
| `TaskDistributor.distribute_batch()` | Distribute multiple tasks                                                  |

---

## Phase 5: Workflow Engine

### Workflow Models (`src/jarvis/workflows/models/workflow.py`)

| Class             | Description                                                                   |
| ----------------- | ----------------------------------------------------------------------------- |
| `StepType`        | Enum: TOOL, INTENT, CONDITION, PARALLEL, LOOP, WAIT, APPROVAL, NOTIFY, SCRIPT |
| `TriggerType`     | Enum: MANUAL, SCHEDULE, FILE_WATCH, WEBHOOK, EVENT, GIT                       |
| `WorkflowStatus`  | Enum: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED                          |
| `WorkflowStep`    | Step definition dataclass                                                     |
| `WorkflowTrigger` | Trigger definition dataclass                                                  |
| `Workflow`        | Workflow definition dataclass                                                 |
| `WorkflowRun`     | Runtime execution dataclass                                                   |
| `StepResult`      | Step execution result                                                         |

### Workflow Parser (`src/jarvis/workflows/parser.py`)

| Function                      | Description              |
| ----------------------------- | ------------------------ |
| `WorkflowParser.parse_file()` | Parse workflow from file |
| `WorkflowParser.parse_yaml()` | Parse YAML content       |
| `WorkflowParser.parse_json()` | Parse JSON content       |
| `WorkflowParser.validate()`   | Validate workflow        |

### Workflow Executor (`src/jarvis/workflows/executor.py`)

| Function                                    | Description            |
| ------------------------------------------- | ---------------------- |
| `WorkflowExecutor.execute()`                | Execute a workflow     |
| `WorkflowExecutor.execute_step()`           | Execute single step    |
| `WorkflowExecutor.execute_tool_step()`      | Execute tool step      |
| `WorkflowExecutor.execute_parallel_step()`  | Execute parallel steps |
| `WorkflowExecutor.execute_loop_step()`      | Execute loop step      |
| `WorkflowExecutor.execute_condition_step()` | Execute condition      |

### Workflow Triggers (`src/jarvis/workflows/triggers.py`)

| Class/Function                   | Description        |
| -------------------------------- | ------------------ |
| `BaseTrigger`                    | Base trigger class |
| `ScheduleTrigger.start()`        | Start cron trigger |
| `ScheduleTrigger.stop()`         | Stop cron trigger  |
| `ScheduleTrigger.get_next_run()` | Get next run time  |
| `FileWatchTrigger.start()`       | Start file watcher |
| `FileWatchTrigger.stop()`        | Stop file watcher  |
| `TriggerManager.register()`      | Register a trigger |
| `TriggerManager.start_all()`     | Start all triggers |
| `TriggerManager.stop_all()`      | Stop all triggers  |

### Workflow Engine (`src/jarvis/workflows/engine.py`)

| Function                          | Description         |
| --------------------------------- | ------------------- |
| `WorkflowEngine.register()`       | Register a workflow |
| `WorkflowEngine.load_from_file()` | Load from file      |
| `WorkflowEngine.run()`            | Run a workflow      |
| `WorkflowEngine.get_status()`     | Get run status      |
| `WorkflowEngine.cancel()`         | Cancel a run        |
| `WorkflowEngine.list_workflows()` | List workflows      |
| `WorkflowEngine.list_runs()`      | List all runs       |

---

## Phase 6: IDE Integration

### IDE Models (`src/jarvis/ide/models.py`)

| Class                | Description                        |
| -------------------- | ---------------------------------- |
| `IDEType`            | Enum: VSCODE, CURSOR, NEOVIM, etc. |
| `DiagnosticSeverity` | Enum: ERROR, WARNING, INFO, HINT   |
| `Position`           | Line/character position            |
| `Range`              | Start/end range                    |
| `Diagnostic`         | Error/warning info                 |
| `TextEdit`           | Text modification                  |
| `FileEdit`           | File-level edits                   |
| `Symbol`             | Code symbol                        |
| `CompletionItem`     | Autocomplete item                  |
| `IDECommand`         | IDE command                        |
| `WorkspaceInfo`      | Workspace details                  |

### VS Code Adapter (`src/jarvis/ide/adapters/vscode.py`)

| Function                             | Description             |
| ------------------------------------ | ----------------------- |
| `VSCodeAdapter.connect()`            | Connect to VS Code      |
| `VSCodeAdapter.disconnect()`         | Disconnect              |
| `VSCodeAdapter.open_file()`          | Open file at position   |
| `VSCodeAdapter.get_diagnostics()`    | Get errors/warnings     |
| `VSCodeAdapter.apply_edit()`         | Apply code edits        |
| `VSCodeAdapter.run_in_terminal()`    | Run in terminal         |
| `VSCodeAdapter.execute_command()`    | Execute VS Code command |
| `VSCodeAdapter.show_message()`       | Show notification       |
| `VSCodeAdapter.get_workspace_info()` | Get workspace info      |

### Cursor Adapter (`src/jarvis/ide/adapters/cursor.py`)

| Function                             | Description        |
| ------------------------------------ | ------------------ |
| Inherits all VS Code functions       |
| `CursorAdapter.get_ai_suggestions()` | Get AI suggestions |

### IDE Manager (`src/jarvis/ide/manager.py`)

| Function                       | Description         |
| ------------------------------ | ------------------- |
| `IDEManager.get_adapter()`     | Get IDE adapter     |
| `IDEManager.set_active()`      | Set active IDE      |
| `IDEManager.list_available()`  | List available IDEs |
| `IDEManager.connect()`         | Connect to IDE      |
| `IDEManager.open_file()`       | Open file           |
| `IDEManager.get_diagnostics()` | Get diagnostics     |
| `IDEManager.apply_edit()`      | Apply edits         |
| `IDEManager.goto_error()`      | Navigate to error   |
| `IDEManager.insert_text()`     | Insert text         |
| `IDEManager.replace_text()`    | Replace text        |
| `IDEManager.get_all_errors()`  | Get all errors      |
| `IDEManager.fix_diagnostic()`  | Apply fix           |

---

## Phase 7: Observability

### Metrics (`src/jarvis/observability/metrics.py`)

| Class/Function                | Description                              |
| ----------------------------- | ---------------------------------------- |
| `MetricType`                  | Enum: COUNTER, GAUGE, HISTOGRAM, SUMMARY |
| `Counter.inc()`               | Increment counter                        |
| `Counter.get()`               | Get counter value                        |
| `Gauge.set()`                 | Set gauge value                          |
| `Gauge.inc()`                 | Increment gauge                          |
| `Gauge.dec()`                 | Decrement gauge                          |
| `Gauge.get()`                 | Get gauge value                          |
| `Histogram.observe()`         | Record observation                       |
| `Histogram.time()`            | Context manager for timing               |
| `Histogram.get_count()`       | Get observation count                    |
| `Histogram.get_sum()`         | Get sum of observations                  |
| `MetricsRegistry.counter()`   | Create counter                           |
| `MetricsRegistry.gauge()`     | Create gauge                             |
| `MetricsRegistry.histogram()` | Create histogram                         |
| `MetricsRegistry.collect()`   | Collect all metrics                      |

### Pre-defined Metrics

| Metric                            | Type      | Description        |
| --------------------------------- | --------- | ------------------ |
| `jarvis_requests_total`           | Counter   | Total API requests |
| `jarvis_request_duration_seconds` | Histogram | Request latency    |
| `jarvis_active_tasks`             | Gauge     | Active tasks       |
| `jarvis_tool_executions_total`    | Counter   | Tool executions    |
| `jarvis_tool_duration_seconds`    | Histogram | Tool latency       |
| `jarvis_memory_bytes`             | Gauge     | Memory usage       |
| `jarvis_llm_requests_total`       | Counter   | LLM requests       |
| `jarvis_llm_tokens_total`         | Counter   | Token usage        |
| `jarvis_workflow_runs_total`      | Counter   | Workflow runs      |
| `jarvis_device_tasks_total`       | Counter   | Device tasks       |

### Tracing (`src/jarvis/observability/tracing.py`)

| Class/Function             | Description                                        |
| -------------------------- | -------------------------------------------------- |
| `SpanKind`                 | Enum: INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER |
| `SpanStatus`               | Enum: UNSET, OK, ERROR                             |
| `Span.set_attribute()`     | Set span attribute                                 |
| `Span.add_event()`         | Add span event                                     |
| `Span.set_status()`        | Set span status                                    |
| `Span.end()`               | End span                                           |
| `Tracer.start_span()`      | Start new span                                     |
| `Tracer.get_active_span()` | Get active span                                    |
| `@trace()`                 | Decorator for auto-tracing                         |

### Dashboard (`src/jarvis/observability/dashboard.py`)

| Function                                    | Description           |
| ------------------------------------------- | --------------------- |
| `DashboardAggregator.get_system_stats()`    | Get system statistics |
| `DashboardAggregator.get_all_health()`      | Get health status     |
| `DashboardAggregator.get_dashboard_data()`  | Get full dashboard    |
| `DashboardAggregator.get_recent_activity()` | Get recent activity   |

---

## API Endpoints

### Agent Endpoints

- `POST /api/v1/agent/chat` - Chat with agent
- `POST /api/v1/agent/execute` - Execute action
- `GET /api/v1/agent/history` - Get history

### Tool Endpoints

- `GET /api/v1/tools` - List tools
- `GET /api/v1/tools/{name}` - Get tool
- `POST /api/v1/tools/{name}/execute` - Execute tool

### System Endpoints

- `GET /api/v1/system/info` - System info
- `GET /api/v1/system/status` - System status

### Memory Endpoints

- `POST /api/v1/memory/store` - Store memory
- `POST /api/v1/memory/search` - Search memory
- `DELETE /api/v1/memory/{id}` - Delete memory

### Self-Heal Endpoints

- `GET /api/v1/self-heal/health` - Health check
- `GET /api/v1/self-heal/issues` - List issues
- `POST /api/v1/self-heal/resolve/{id}` - Resolve issue

### Device Endpoints

- `GET /api/v1/devices` - List devices
- `GET /api/v1/devices/{id}` - Get device
- `POST /api/v1/devices/{id}/task` - Assign task
- `WS /api/v1/devices/ws` - WebSocket

### Workflow Endpoints

- `GET /api/v1/workflows` - List workflows
- `POST /api/v1/workflows` - Create workflow
- `POST /api/v1/workflows/{id}/run` - Run workflow
- `GET /api/v1/workflows/{id}/status` - Get status

### IDE Endpoints

- `GET /api/v1/ide/adapters` - List adapters
- `POST /api/v1/ide/open` - Open file
- `GET /api/v1/ide/diagnostics` - Get diagnostics
- `POST /api/v1/ide/edit` - Apply edits

### Observability Endpoints

- `GET /api/v1/observability/metrics` - Get metrics
- `GET /api/v1/observability/prometheus` - Prometheus format
- `GET /api/v1/observability/traces` - Get traces
- `GET /api/v1/observability/dashboard` - Dashboard data

---

## Built-in Tools

| Tool Name       | Module     | Description        |
| --------------- | ---------- | ------------------ |
| `file_read`     | file.py    | Read file contents |
| `file_write`    | file.py    | Write to file      |
| `file_delete`   | file.py    | Delete file        |
| `file_list`     | file.py    | List directory     |
| `shell_execute` | shell.py   | Run shell command  |
| `git_status`    | git.py     | Git status         |
| `git_diff`      | git.py     | Git diff           |
| `git_commit`    | git.py     | Git commit         |
| `git_push`      | git.py     | Git push           |
| `git_pull`      | git.py     | Git pull           |
| `docker_ps`     | docker.py  | List containers    |
| `docker_build`  | docker.py  | Build image        |
| `docker_run`    | docker.py  | Run container      |
| `system_info`   | system.py  | System information |
| `process_list`  | process.py | List processes     |
| `process_kill`  | process.py | Kill process       |
| `log_tail`      | log.py     | Tail log file      |
| `log_search`    | log.py     | Search logs        |
| `vscode_open`   | vscode.py  | Open in VS Code    |

---

## Summary Statistics

| Category                | Count |
| ----------------------- | ----- |
| Total Modules           | 25+   |
| Total Functions         | 150+  |
| API Endpoints           | 90+   |
| Built-in Tools          | 18+   |
| Monitor Types           | 4     |
| Resolver Types          | 4     |
| IDE Adapters            | 2     |
| Metric Types            | 3     |
| Workflow Step Types     | 9     |
| Trigger Types           | 6     |
| Load Balance Strategies | 5     |
