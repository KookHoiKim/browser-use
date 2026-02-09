"""Multi-agent orchestration layer for browser-use.

This module provides scalable multi-agent coordination capabilities,
allowing multiple AI agents to collaborate on web automation tasks.
"""

from browser_use.orchestration.agent_registry import AgentRegistry, ManagedAgent
from browser_use.orchestration.config import ConfigLoader
from browser_use.orchestration.events import (
	AgentRegisteredEvent,
	AgentStatusChangedEvent,
	DelegationRequestEvent,
	MessageReceivedEvent,
	MessageSentEvent,
	OrchestrationCompletedEvent,
	OrchestrationEvent,
	OrchestrationStartedEvent,
	TaskAssignedEvent,
	TaskCompletedEvent,
	TaskFailedEvent,
	TaskStartedEvent,
)
from browser_use.orchestration.llm_provider import LLMProviderFactory, LLMProviderRegistry
from browser_use.orchestration.service import Orchestrator
from browser_use.orchestration.views import (
	AgentCapability,
	AgentConfig,
	AgentMessage,
	AgentRole,
	AgentStatus,
	LLMProviderConfig,
	LLMProviderType,
	OrchestrationConfig,
	OrchestrationState,
	ProxyConfig,
	TaskConfig,
	TaskPriority,
	TaskResult,
)

__all__ = [
	# Core services
	'Orchestrator',
	'ConfigLoader',
	# Registries
	'AgentRegistry',
	'ManagedAgent',
	'LLMProviderRegistry',
	'LLMProviderFactory',
	# Configuration models
	'OrchestrationConfig',
	'AgentConfig',
	'LLMProviderConfig',
	'TaskConfig',
	'ProxyConfig',
	'AgentCapability',
	# Enums
	'AgentRole',
	'AgentStatus',
	'LLMProviderType',
	'TaskPriority',
	# State and results
	'OrchestrationState',
	'TaskResult',
	'AgentMessage',
	# Events
	'OrchestrationEvent',
	'AgentRegisteredEvent',
	'AgentStatusChangedEvent',
	'TaskAssignedEvent',
	'TaskStartedEvent',
	'TaskCompletedEvent',
	'TaskFailedEvent',
	'MessageSentEvent',
	'MessageReceivedEvent',
	'DelegationRequestEvent',
	'OrchestrationStartedEvent',
	'OrchestrationCompletedEvent',
]
