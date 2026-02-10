"""Pydantic models for multi-agent orchestration system."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid_extensions import uuid7str


class AgentRole(str, Enum):
	"""Predefined agent roles for web-based multi-agent orchestration."""

	PLANNER = 'planner'
	RESEARCHER = 'researcher'
	NAVIGATOR = 'navigator'
	FORM_FILLER = 'form_filler'
	DATA_EXTRACTOR = 'data_extractor'
	VALIDATOR = 'validator'
	COORDINATOR = 'coordinator'
	CUSTOM = 'custom'


class AgentStatus(str, Enum):
	"""Agent execution status."""

	IDLE = 'idle'
	THINKING = 'thinking'
	ACTING = 'acting'
	WAITING = 'waiting'
	COMPLETED = 'completed'
	FAILED = 'failed'


class TaskPriority(str, Enum):
	"""Task priority levels."""

	LOW = 'low'
	MEDIUM = 'medium'
	HIGH = 'high'
	CRITICAL = 'critical'


class LLMProviderType(str, Enum):
	"""Supported LLM provider types."""

	OPENAI = 'openai'
	AZURE = 'azure'
	ANTHROPIC = 'anthropic'
	VLLM = 'vllm'
	GOOGLE = 'google'
	GROQ = 'groq'
	CUSTOM = 'custom'


class ProxyConfig(BaseModel):
	"""Proxy configuration for LLM requests."""

	model_config = ConfigDict(extra='forbid', validate_assignment=True)

	enabled: bool = False
	http_proxy: str | None = None
	https_proxy: str | None = None
	no_proxy: list[str] | None = None

	@field_validator('http_proxy', 'https_proxy')
	@classmethod
	def validate_proxy_url(cls, v: str | None) -> str | None:
		if v is not None and not v.startswith(('http://', 'https://', 'socks5://')):
			raise ValueError(f'Proxy URL must start with http://, https://, or socks5://: {v}')
		return v


class LLMProviderConfig(BaseModel):
	"""Configuration for an LLM provider."""

	model_config = ConfigDict(extra='forbid', validate_assignment=True)

	name: str = Field(..., description='Unique identifier for this LLM provider')
	provider_type: LLMProviderType = Field(..., description='Type of LLM provider')
	model_name: str = Field(..., description='Model name to use')

	# Connection details
	api_base: str | None = Field(None, description='Base URL for API requests')
	api_key: str | None = Field(None, description='API key for authentication')
	api_version: str | None = Field(None, description='API version (for Azure)')

	# Azure-specific
	azure_deployment: str | None = Field(None, description='Azure deployment name')

	# Proxy configuration
	proxy: ProxyConfig = Field(default_factory=ProxyConfig)

	# Request parameters
	temperature: float = Field(0.7, ge=0.0, le=2.0)
	max_tokens: int | None = Field(None, gt=0)
	timeout: int = Field(120, gt=0, description='Request timeout in seconds')

	# Rate limiting
	max_retries: int = Field(3, ge=0)
	rate_limit_delay: float = Field(1.0, ge=0.0)


class AgentCapability(BaseModel):
	"""Defines a capability that an agent possesses."""

	model_config = ConfigDict(extra='forbid')

	name: str = Field(..., description='Capability name')
	description: str = Field(..., description='What this capability enables')
	parameters: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
	"""Configuration for a single agent in the orchestration system."""

	model_config = ConfigDict(extra='forbid', validate_assignment=True)

	id: str = Field(default_factory=uuid7str, description='Unique agent ID')
	name: str = Field(..., description='Human-readable agent name')
	role: AgentRole = Field(..., description='Agent role')
	description: str = Field(..., description='Agent purpose and responsibilities')

	# LLM configuration
	llm_provider: str = Field(..., description='Name of LLM provider to use')

	# Agent capabilities
	capabilities: list[AgentCapability] = Field(default_factory=list)

	# System prompt components
	system_prompt: str | None = Field(None, description='Custom system prompt')
	include_browser_actions: bool = Field(True, description='Include browser action tools')

	# Execution settings
	max_steps: int = Field(100, gt=0, description='Maximum execution steps')
	max_retry_attempts: int = Field(3, ge=0)
	timeout: int = Field(300, gt=0, description='Agent timeout in seconds')

	# Collaboration settings
	can_delegate: bool = Field(True, description='Can delegate tasks to other agents')
	can_receive_delegations: bool = Field(True, description='Can accept delegated tasks')
	delegation_roles: list[AgentRole] = Field(
		default_factory=list, description='Roles this agent can delegate to'
	)


class TaskConfig(BaseModel):
	"""Configuration for a task in the orchestration system."""

	model_config = ConfigDict(extra='forbid', validate_assignment=True)

	id: str = Field(default_factory=uuid7str)
	description: str = Field(..., description='Task description')
	assigned_agent: str | None = Field(None, description='Agent ID to execute this task')
	priority: TaskPriority = Field(TaskPriority.MEDIUM)
	dependencies: list[str] = Field(default_factory=list, description='Task IDs this depends on')
	context: dict[str, Any] = Field(default_factory=dict)
	max_retries: int = Field(3, ge=0)


class OrchestrationConfig(BaseModel):
	"""Main configuration for the multi-agent orchestration system."""

	model_config = ConfigDict(extra='forbid', validate_assignment=True)

	# LLM providers
	llm_providers: list[LLMProviderConfig] = Field(
		..., min_length=1, description='Available LLM providers'
	)

	# Agents
	agents: list[AgentConfig] = Field(..., min_length=1, description='Agent configurations')

	# Orchestration settings
	coordinator_agent: str | None = Field(
		None, description='Agent ID to act as coordinator (uses first agent if None)'
	)
	max_concurrent_agents: int = Field(3, ge=1, le=10)
	enable_agent_communication: bool = Field(True)
	communication_protocol: Literal['direct', 'broadcast', 'coordinator'] = Field('coordinator')

	# Task management
	enable_task_queue: bool = Field(True)
	task_retry_delay: float = Field(2.0, ge=0.0)

	# Browser settings (inherited from browser-use)
	shared_browser: bool = Field(
		False, description='Whether agents share a single browser instance'
	)

	@field_validator('agents')
	@classmethod
	def validate_agents(cls, v: list[AgentConfig]) -> list[AgentConfig]:
		"""Ensure agent names are unique."""
		names = [agent.name for agent in v]
		if len(names) != len(set(names)):
			raise ValueError('Agent names must be unique')
		return v

	@field_validator('llm_providers')
	@classmethod
	def validate_llm_providers(cls, v: list[LLMProviderConfig]) -> list[LLMProviderConfig]:
		"""Ensure LLM provider names are unique."""
		names = [provider.name for provider in v]
		if len(names) != len(set(names)):
			raise ValueError('LLM provider names must be unique')
		return v


class AgentMessage(BaseModel):
	"""Message passed between agents."""

	model_config = ConfigDict(extra='forbid')

	id: str = Field(default_factory=uuid7str)
	from_agent: str = Field(..., description='Sender agent ID')
	to_agent: str | None = Field(None, description='Recipient agent ID (None for broadcast)')
	message_type: Literal['task', 'result', 'query', 'response', 'notification'] = Field(...)
	content: dict[str, Any] = Field(...)
	timestamp: float = Field(...)
	requires_response: bool = Field(False)
	parent_message_id: str | None = Field(None)


class TaskResult(BaseModel):
	"""Result of a task execution."""

	model_config = ConfigDict(extra='forbid')

	task_id: str
	agent_id: str
	status: Literal['success', 'failure', 'partial']
	output: dict[str, Any] = Field(default_factory=dict)
	error: str | None = None
	execution_time: float
	steps_taken: int
	metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationState(BaseModel):
	"""Current state of the orchestration system."""

	model_config = ConfigDict(extra='forbid')

	session_id: str = Field(default_factory=uuid7str)
	active_agents: dict[str, AgentStatus] = Field(default_factory=dict)
	pending_tasks: list[str] = Field(default_factory=list)
	completed_tasks: list[str] = Field(default_factory=list)
	failed_tasks: list[str] = Field(default_factory=list)
	message_queue: list[AgentMessage] = Field(default_factory=list)
	results: list[TaskResult] = Field(default_factory=list)
	start_time: float | None = None
	end_time: float | None = None
