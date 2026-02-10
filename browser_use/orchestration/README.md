

# Multi-Agent Orchestration Layer

This module provides a scalable multi-agent orchestration system for browser-use, enabling multiple AI agents to collaborate on complex web automation tasks.

## Overview

The orchestration layer allows you to:

- **Define multiple specialized agents** with different roles and capabilities
- **Configure LLM providers** with proxy support (vLLM, Azure GPT, OpenAI, etc.)
- **Coordinate task execution** with dependencies and priorities
- **Enable inter-agent communication** for collaborative workflows
- **Monitor and track** agent performance and task completion

## Architecture

### Key Components

1. **Orchestrator** (`service.py`): Main coordination service that manages agents, tasks, and execution flow
2. **AgentRegistry** (`agent_registry.py`): Manages agent instances and their lifecycle
3. **LLMProviderRegistry** (`llm_provider.py`): Handles LLM provider creation with proxy support
4. **ConfigLoader** (`config.py`): Loads and validates YAML configuration files
5. **Event System** (`events.py`): Event-driven coordination between agents

### Agent Roles

The system supports various predefined roles:

- **Coordinator**: High-level planning and delegation
- **Planner**: Strategic workflow design
- **Researcher**: Information gathering and analysis
- **Navigator**: Page navigation and element interaction
- **Form Filler**: Form completion and submission
- **Data Extractor**: Structured data extraction
- **Validator**: Quality assurance and verification
- **Custom**: User-defined roles

## Configuration

### YAML Configuration

Create a YAML file to configure your multi-agent system:

```yaml
# LLM Providers
llm_providers:
  - name: vllm_qwen
    provider_type: vllm
    model_name: Qwen3VL_32b
    api_base: http://127.0.0.1:3333/v1
    api_key: EMPTY
    temperature: 0.7
    max_tokens: 4096
    proxy:
      enabled: false

  - name: azure_gpt4
    provider_type: azure
    model_name: gpt-4
    azure_deployment: ${AZURE_DEPLOYMENT_NAME}
    api_key: ${AZURE_API_KEY}
    api_base: ${AZURE_API_BASE}
    api_version: "2024-02-15-preview"
    proxy:
      enabled: true
      http_proxy: http://127.0.0.1:9090
      https_proxy: http://127.0.0.1:9090

# Agents
agents:
  - name: coordinator
    role: coordinator
    description: "Coordinates tasks across agents"
    llm_provider: azure_gpt4
    max_steps: 50
    can_delegate: true
    delegation_roles:
      - planner
      - researcher
      - navigator

  - name: navigator
    role: navigator
    description: "Navigates web pages"
    llm_provider: vllm_qwen
    max_steps: 200
    can_receive_delegations: true

# Orchestration Settings
max_concurrent_agents: 3
enable_agent_communication: true
shared_browser: false

# Sequence Settings (optional)
# When enabled, each task is executed by the listed agents in order.
sequence:
  enabled: false
  steps:
    - planner
    - navigator
    - data_extractor
  pass_context: true
  stop_on_failure: true
```

When `sequence` is disabled, tasks are queued and assigned to the first available idle agent.
You can still force a task to run on a specific agent by setting `assigned_agent` on `TaskConfig`.

### Environment Variables

Use environment variable substitution in your config:

- `${VAR_NAME}` - Required variable (fails if not set)
- `${VAR_NAME:default}` - Optional with default value

### Proxy Configuration

Configure proxies for LLM requests:

```yaml
proxy:
  enabled: true
  http_proxy: http://127.0.0.1:9090
  https_proxy: http://127.0.0.1:9090
  no_proxy:
    - localhost
    - 127.0.0.1
```

## Usage

### Basic Example

```python
import asyncio
from pathlib import Path
from browser_use.orchestration import (
    ConfigLoader,
    Orchestrator,
    TaskConfig,
    TaskPriority,
)

async def main():
    # Load configuration
    config = ConfigLoader.load_config('config.yaml')

    # Create orchestrator
    orchestrator = Orchestrator(config)
    await orchestrator.initialize()

    # Define tasks
    tasks = [
        TaskConfig(
            description='Navigate to https://example.com',
            priority=TaskPriority.HIGH,
        ),
        TaskConfig(
            description='Extract page title and links',
            priority=TaskPriority.MEDIUM,
        ),
    ]

    try:
        # Run orchestration
        final_state = await orchestrator.run(tasks)

        # Print results
        print(f"Completed: {len(final_state.completed_tasks)}")
        print(f"Failed: {len(final_state.failed_tasks)}")

    finally:
        await orchestrator.shutdown()

asyncio.run(main())
```

### Task Dependencies

Create workflows with task dependencies:

```python
task1 = TaskConfig(
    description='Research web automation tools',
    priority=TaskPriority.HIGH,
)

task2 = TaskConfig(
    description='Navigate to top tool websites',
    dependencies=[task1.id],  # Depends on task1
)

task3 = TaskConfig(
    description='Compare and summarize findings',
    dependencies=[task2.id],  # Depends on task2
)
```

### Event-Driven Coordination

Register event handlers for orchestration events:

```python
@orchestrator.event_bus.on('task_started')
async def on_task_started(event):
    print(f"Task {event.task_id} started by {event.agent_id}")

@orchestrator.event_bus.on('task_completed')
async def on_task_completed(event):
    print(f"Task {event.task_id} completed in {event.result.execution_time:.2f}s")

@orchestrator.event_bus.on('agent_status_changed')
async def on_status_changed(event):
    print(f"Agent {event.agent_id}: {event.old_status} → {event.new_status}")
```

### Programmatic Configuration

Create configuration programmatically instead of using YAML:

```python
from browser_use.orchestration import (
    AgentConfig,
    AgentRole,
    LLMProviderConfig,
    LLMProviderType,
    OrchestrationConfig,
)

# Create LLM provider
llm_provider = LLMProviderConfig(
    name='my_provider',
    provider_type=LLMProviderType.VLLM,
    model_name='Qwen3VL_32b',
    api_base='http://127.0.0.1:3333/v1',
)

# Create agent
agent = AgentConfig(
    name='my_agent',
    role=AgentRole.NAVIGATOR,
    description='Custom navigation agent',
    llm_provider='my_provider',
    max_steps=100,
)

# Create orchestration config
config = OrchestrationConfig(
    llm_providers=[llm_provider],
    agents=[agent],
    max_concurrent_agents=1,
)

# Use config with orchestrator
orchestrator = Orchestrator(config)
```

## LLM Provider Support

### Supported Providers

- **OpenAI**: GPT-4, GPT-4o, etc.
- **Azure OpenAI**: Azure-hosted models with API versioning
- **Anthropic**: Claude models
- **vLLM**: Self-hosted models (OpenAI-compatible API)
- **Google**: Gemini models
- **Groq**: Groq-hosted models

### Provider Configuration Examples

#### vLLM (Local Model)

```yaml
llm_providers:
  - name: local_model
    provider_type: vllm
    model_name: Qwen3VL_32b
    api_base: http://127.0.0.1:3333/v1
    api_key: EMPTY
```

#### Azure with Proxy

```yaml
llm_providers:
  - name: azure_gpt
    provider_type: azure
    model_name: gpt-4
    azure_deployment: my-deployment
    api_key: ${AZURE_API_KEY}
    api_base: https://my-resource.openai.azure.com
    api_version: "2024-02-15-preview"
    proxy:
      enabled: true
      http_proxy: http://127.0.0.1:9090
      https_proxy: http://127.0.0.1:9090
```

#### OpenAI

```yaml
llm_providers:
  - name: openai_gpt4
    provider_type: openai
    model_name: gpt-4o
    api_key: ${OPENAI_API_KEY}
```

## Agent Capabilities

Define custom capabilities for agents:

```yaml
agents:
  - name: scraper
    role: data_extractor
    description: "E-commerce data extraction"
    llm_provider: vllm_qwen
    capabilities:
      - name: price_extraction
        description: "Extract product prices"
        parameters:
          currency_formats: [USD, EUR, GBP]
      - name: review_analysis
        description: "Analyze reviews and ratings"
```

## Monitoring and Statistics

Get real-time statistics:

```python
# Overall orchestration stats
stats = orchestrator.get_stats()
print(f"Active tasks: {stats['tasks']['active']}")
print(f"Completed: {stats['tasks']['completed']}")
print(f"Total agents: {stats['agents']['total_agents']}")

# Per-agent statistics
agent_stats = orchestrator.agent_registry.get_all_stats()
for agent in agent_stats['agents']:
    print(f"{agent['name']}: {agent['tasks_completed']} tasks completed")
```

## Best Practices

### 1. Agent Role Selection

- Use **Coordinator** for high-level orchestration
- Use **Navigator** for page interaction tasks
- Use **Researcher** for information gathering
- Use **Data Extractor** for structured data extraction
- Use **Validator** to verify task completion

### 2. Task Design

- Break complex tasks into smaller subtasks
- Use task dependencies for sequential workflows
- Set appropriate priorities for critical tasks
- Provide context data when needed

### 3. LLM Provider Selection

- Use powerful models (GPT-4, Claude) for coordinators
- Use faster models (vLLM, GPT-4o-mini) for simple tasks
- Configure proxies for enterprise environments
- Set appropriate timeouts and retry limits

### 4. Browser Management

- Use `shared_browser: false` for parallel agent execution
- Use `shared_browser: true` to reduce resource usage
- Set `max_concurrent_agents` based on system resources

### 5. Error Handling

- Set appropriate `max_retry_attempts` for agents
- Use `task_retry_delay` to avoid overwhelming services
- Monitor events to detect and handle failures

## Testing

Run orchestration tests:

```bash
# Run all orchestration tests
uv run pytest -vxs tests/ci/test_orchestration.py

# Run specific test
uv run pytest -vxs tests/ci/test_orchestration.py::test_orchestrator_initialization
```

## Examples

See `examples/multi_agent_orchestration.py` for comprehensive examples:

```bash
# Simple example
python examples/multi_agent_orchestration.py simple

# Complex with dependencies
python examples/multi_agent_orchestration.py complex

# Event-driven coordination
python examples/multi_agent_orchestration.py events

# Custom agent configuration
python examples/multi_agent_orchestration.py custom
```

## Integration with OS-Symphony

This orchestration layer is inspired by [OS-Symphony](https://github.com/OS-Copilot/OS-Symphony) but adapted for web-based automation:

- **Excluded**: OS-specific operations (file system, terminal, etc.)
- **Included**: Multi-agent coordination, task decomposition, delegation patterns
- **Extended**: Web-specific agent roles, browser management, DOM interaction

## API Reference

### Core Classes

- `Orchestrator`: Main orchestration service
- `ConfigLoader`: YAML configuration loader
- `AgentRegistry`: Agent management
- `LLMProviderRegistry`: LLM provider management

### Configuration Models

- `OrchestrationConfig`: Main configuration
- `AgentConfig`: Agent configuration
- `LLMProviderConfig`: LLM provider configuration
- `TaskConfig`: Task configuration

### Events

- `OrchestrationStartedEvent`
- `TaskAssignedEvent`
- `TaskStartedEvent`
- `TaskCompletedEvent`
- `TaskFailedEvent`
- `AgentStatusChangedEvent`
- `OrchestrationCompletedEvent`

See inline documentation for detailed API reference.
