# Multi-Agent Orchestration Integration Plan

## Overview

This document describes the integration of OS-Symphony-inspired multi-agent orchestration capabilities into browser-use. The implementation provides a scalable, YAML-configurable system for coordinating multiple AI agents on web automation tasks.

## Architecture Summary

### Design Principles

1. **Modular Architecture**: Orchestration layer is completely separate from core browser-use functionality
2. **Configuration-Driven**: All agent definitions and LLM providers managed via YAML
3. **Event-Driven Coordination**: Agents communicate through an event bus system
4. **Extensible Roles**: Easy to add new agent roles and capabilities
5. **Proxy Support**: First-class support for enterprise proxy requirements

### Integration Approach

The orchestration layer sits **above** browser-use's existing agent system:

```
┌─────────────────────────────────────────┐
│   Orchestrator (Multi-Agent Coordinator)│
│   - Task decomposition                  │
│   - Agent assignment                    │
│   - Inter-agent communication           │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┬──────────────┐
    ▼                     ▼              ▼
┌────────┐          ┌────────┐      ┌────────┐
│Agent 1 │          │Agent 2 │      │Agent N │
│(vLLM)  │          │(Azure) │      │(GPT-4) │
└───┬────┘          └───┬────┘      └───┬────┘
    │                   │                │
    └───────────────────┴────────────────┘
                        ▼
              ┌──────────────────┐
              │  Browser Session │
              │  (Shared/Isolated)│
              └──────────────────┘
```

## Directory Structure

```
browser-use/
├── browser_use/
│   ├── orchestration/              # New orchestration module
│   │   ├── __init__.py            # Public API exports
│   │   ├── README.md              # Orchestration documentation
│   │   ├── views.py               # Pydantic models (config, state, events)
│   │   ├── config.py              # YAML configuration loader
│   │   ├── llm_provider.py        # LLM provider factory with proxy support
│   │   ├── agent_registry.py      # Agent lifecycle management
│   │   ├── service.py             # Core Orchestrator service
│   │   └── events.py              # Event definitions
│   ├── agent/                     # Existing browser-use agent (unchanged)
│   ├── browser/                   # Existing browser management (unchanged)
│   └── ...
├── examples/
│   ├── orchestration_config.yaml  # Example configuration file
│   └── multi_agent_orchestration.py  # Usage examples
├── tests/
│   └── ci/
│       └── test_orchestration.py  # Integration tests
└── pyproject.toml                 # Updated with pyyaml dependency
```

## Key Components

### 1. Configuration System (`config.py`)

**Purpose**: Load and validate YAML configuration with environment variable support

**Features**:
- Environment variable substitution: `${VAR_NAME}` or `${VAR_NAME:default}`
- Validation of provider/agent references
- Type-safe Pydantic models

**Example**:
```yaml
llm_providers:
  - name: vllm_qwen
    provider_type: vllm
    model_name: Qwen3VL_32b
    api_base: http://127.0.0.1:3333/v1
```

### 2. LLM Provider Factory (`llm_provider.py`)

**Purpose**: Create LLM providers with proxy support

**Supported Providers**:
- vLLM (local models)
- Azure OpenAI (with proxy)
- OpenAI
- Anthropic Claude
- Google Gemini
- Groq

**Proxy Configuration**:
```yaml
proxy:
  enabled: true
  http_proxy: http://127.0.0.1:9090
  https_proxy: http://127.0.0.1:9090
  no_proxy: [localhost, 127.0.0.1]
```

### 3. Agent Registry (`agent_registry.py`)

**Purpose**: Manage agent lifecycle and state

**Features**:
- Agent registration by role
- Status tracking (idle, thinking, acting, waiting, completed, failed)
- Statistics collection (tasks completed, execution time, etc.)
- Thread-safe with asyncio locks

### 4. Orchestrator Service (`service.py`)

**Purpose**: Core coordination service

**Features**:
- Task queue management with dependencies
- Concurrent agent execution (configurable limit)
- Automatic task retry on failure
- Event emission for all lifecycle events
- Browser session management (shared or per-agent)

**Workflow**:
1. Load configuration and initialize agents
2. Accept task list with priorities and dependencies
3. Assign tasks to available agents based on role/capability
4. Execute tasks with automatic retry
5. Collect results and emit events
6. Return final state with statistics

### 5. Event System (`events.py`)

**Purpose**: Event-driven coordination

**Event Types**:
- `OrchestrationStartedEvent`
- `AgentRegisteredEvent`
- `TaskAssignedEvent`
- `TaskStartedEvent`
- `TaskCompletedEvent`
- `TaskFailedEvent`
- `AgentStatusChangedEvent`
- `MessageSentEvent`
- `MessageReceivedEvent`
- `OrchestrationCompletedEvent`

### 6. Data Models (`views.py`)

**Core Models**:
- `OrchestrationConfig`: Main configuration
- `LLMProviderConfig`: LLM provider settings
- `AgentConfig`: Agent definition
- `TaskConfig`: Task specification
- `OrchestrationState`: Runtime state
- `TaskResult`: Execution result
- `AgentMessage`: Inter-agent messages

**Enums**:
- `AgentRole`: Agent role types
- `AgentStatus`: Agent execution status
- `LLMProviderType`: Supported providers
- `TaskPriority`: Task priority levels

## Configuration Template

### Complete Configuration Example

```yaml
# Multi-Agent Orchestration Configuration

# LLM Providers
llm_providers:
  # vLLM Provider (Local)
  - name: vllm_qwen
    provider_type: vllm
    model_name: Qwen3VL_32b
    api_base: http://127.0.0.1:3333/v1
    api_key: EMPTY
    temperature: 0.7
    max_tokens: 4096
    timeout: 120
    max_retries: 3
    proxy:
      enabled: false

  # Azure GPT (with Proxy)
  - name: azure_gpt4
    provider_type: azure
    model_name: gpt-4
    azure_deployment: ${AZURE_DEPLOYMENT_NAME}
    api_key: ${AZURE_API_KEY}
    api_base: ${AZURE_API_BASE}
    api_version: "2024-02-15-preview"
    temperature: 0.7
    proxy:
      enabled: true
      http_proxy: http://127.0.0.1:9090
      https_proxy: http://127.0.0.1:9090

# Agents
agents:
  - name: coordinator
    role: coordinator
    description: "High-level task coordination"
    llm_provider: azure_gpt4
    max_steps: 50
    can_delegate: true
    delegation_roles: [planner, navigator, researcher]

  - name: navigator
    role: navigator
    description: "Web page navigation"
    llm_provider: vllm_qwen
    max_steps: 200

# Orchestration Settings
max_concurrent_agents: 3
enable_agent_communication: true
communication_protocol: coordinator
shared_browser: false
```

## Usage Examples

### Basic Usage

```python
from browser_use.orchestration import (
    ConfigLoader,
    Orchestrator,
    TaskConfig,
)

# Load config
config = ConfigLoader.load_config('config.yaml')

# Create orchestrator
orchestrator = Orchestrator(config)
await orchestrator.initialize()

# Define tasks
tasks = [
    TaskConfig(description='Navigate to example.com'),
    TaskConfig(description='Extract page data'),
]

# Run
final_state = await orchestrator.run(tasks)
await orchestrator.shutdown()
```

### With Task Dependencies

```python
task1 = TaskConfig(description='Research topic')
task2 = TaskConfig(
    description='Summarize findings',
    dependencies=[task1.id]  # Wait for task1
)

await orchestrator.run([task1, task2])
```

### Event-Driven

```python
@orchestrator.event_bus.on('task_completed')
async def on_complete(event):
    print(f"Task {event.task_id} done!")

await orchestrator.run(tasks)
```

## Testing

### Test Coverage

The test suite (`tests/ci/test_orchestration.py`) covers:

- ✅ Configuration loading and validation
- ✅ LLM provider creation with proxy support
- ✅ Agent registration and lifecycle
- ✅ Task execution and coordination
- ✅ Event emission and handling
- ✅ Multi-agent coordination
- ✅ Statistics collection

### Running Tests

```bash
# All orchestration tests
uv run pytest -vxs tests/ci/test_orchestration.py

# Specific test
uv run pytest -vxs tests/ci/test_orchestration.py::test_orchestrator_initialization

# With coverage
uv run pytest --cov=browser_use.orchestration tests/ci/test_orchestration.py
```

## Key Technical Requirements ✅

### 1. YAML-Based Configuration ✅

- ✅ All agent configurations in YAML
- ✅ LLM provider settings in YAML
- ✅ Environment variable substitution
- ✅ Validation with Pydantic models

### 2. LLM Provider Integration ✅

- ✅ vLLM support (http://127.0.0.1:3333/v1)
- ✅ Azure GPT with API versioning
- ✅ Proxy configuration (http://127.0.0.1:9090)
- ✅ Multiple provider support
- ✅ httpx-based HTTP client with proxy

### 3. Architectural Approach ✅

- ✅ Modular structure
- ✅ browser-use handles low-level web actions
- ✅ Orchestrator handles high-level coordination
- ✅ Plug-and-play agent system
- ✅ Event-driven communication

### 4. Scalability ✅

- ✅ Extensible agent roles
- ✅ Dynamic agent registration
- ✅ Concurrent agent execution
- ✅ Task queue with priorities
- ✅ Browser session management (shared/isolated)

## OS-Symphony Integration Notes

### Ported Features

From OS-Symphony, we ported:

1. **Multi-Agent Architecture**: Coordinator + specialized agents
2. **Task Decomposition**: Break complex goals into subtasks
3. **Agent Delegation**: Agents can delegate to others
4. **Role-Based Assignment**: Match tasks to agent capabilities

### Excluded Features

We excluded OS-specific operations:

- ❌ File system operations
- ❌ Terminal/shell commands
- ❌ OS-level automation
- ❌ System settings management

### Web-Specific Extensions

We added web-specific features:

- ✅ Browser session management
- ✅ DOM interaction through browser-use
- ✅ Web-focused agent roles (Navigator, FormFiller, DataExtractor)
- ✅ Page state tracking

## Dependencies Added

```toml
dependencies = [
    # ... existing dependencies ...
    "pyyaml>=6.0.2",  # For YAML configuration loading
]
```

All other dependencies (httpx, pydantic, bubus, etc.) were already present in browser-use.

## Next Steps

### For Users

1. **Create configuration file**: Copy `examples/orchestration_config.yaml`
2. **Set environment variables**: Azure keys, model endpoints, proxy settings
3. **Define agents**: Configure roles and LLM providers
4. **Run example**: `python examples/multi_agent_orchestration.py`

### For Developers

1. **Add custom roles**: Extend `AgentRole` enum and implement capabilities
2. **Custom LLM providers**: Add factory methods in `llm_provider.py`
3. **Event handlers**: Register custom event handlers for monitoring
4. **Advanced coordination**: Implement delegation strategies in coordinator agents

## Performance Considerations

- **Concurrent Agents**: Set `max_concurrent_agents` based on system resources
- **Browser Sessions**: Use `shared_browser: false` for true parallelism
- **LLM Selection**: Use faster models (vLLM, GPT-4o-mini) for routine tasks
- **Task Granularity**: Break large tasks into smaller chunks for better parallelism

## Security Considerations

- **API Keys**: Use environment variables, never commit keys to YAML
- **Proxy Configuration**: Validate proxy URLs and use HTTPS where possible
- **Browser Isolation**: Consider security implications of shared vs isolated browsers
- **Network Access**: Review agent access to external resources

## Troubleshooting

### Common Issues

1. **Provider not found**: Check LLM provider name matches in agent config
2. **Proxy connection failed**: Verify proxy is running and accessible
3. **Task hanging**: Check agent `max_steps` and `timeout` settings
4. **Memory issues**: Reduce `max_concurrent_agents` or use `shared_browser: true`

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Monitor events:

```python
@orchestrator.event_bus.on('*')
async def log_all_events(event):
    print(f"Event: {event.event_type}")
```

## Documentation

- **Module README**: `browser_use/orchestration/README.md`
- **Examples**: `examples/multi_agent_orchestration.py`
- **Configuration**: `examples/orchestration_config.yaml`
- **Tests**: `tests/ci/test_orchestration.py`
- **This Document**: Integration plan and architecture

## Summary

The multi-agent orchestration layer successfully integrates OS-Symphony-inspired coordination capabilities into browser-use, providing:

- ✅ **Scalable multi-agent system** with role-based specialization
- ✅ **YAML-driven configuration** with environment variable support
- ✅ **Proxy-enabled LLM providers** (vLLM, Azure, OpenAI, etc.)
- ✅ **Event-driven coordination** with comprehensive monitoring
- ✅ **Plug-and-play architecture** for easy extensibility
- ✅ **Production-ready** with full test coverage

The implementation is modular, well-tested, and ready for use in web-based multi-agent automation scenarios.
