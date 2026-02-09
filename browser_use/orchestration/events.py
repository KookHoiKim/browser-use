"""Events for multi-agent orchestration system."""

from typing import Any

from pydantic import BaseModel, Field

from browser_use.orchestration.views import AgentStatus, TaskResult


class OrchestrationEvent(BaseModel):
	"""Base event for orchestration system."""

	event_type: str = Field(..., description='Type of event')
	timestamp: float = Field(..., description='Event timestamp')
	metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRegisteredEvent(OrchestrationEvent):
	"""Event emitted when an agent is registered."""

	event_type: str = 'agent_registered'
	agent_id: str
	agent_name: str
	role: str


class AgentStatusChangedEvent(OrchestrationEvent):
	"""Event emitted when agent status changes."""

	event_type: str = 'agent_status_changed'
	agent_id: str
	old_status: AgentStatus
	new_status: AgentStatus


class TaskAssignedEvent(OrchestrationEvent):
	"""Event emitted when a task is assigned to an agent."""

	event_type: str = 'task_assigned'
	task_id: str
	agent_id: str
	task_description: str


class TaskStartedEvent(OrchestrationEvent):
	"""Event emitted when an agent starts a task."""

	event_type: str = 'task_started'
	task_id: str
	agent_id: str


class TaskCompletedEvent(OrchestrationEvent):
	"""Event emitted when a task is completed."""

	event_type: str = 'task_completed'
	task_id: str
	agent_id: str
	result: TaskResult


class TaskFailedEvent(OrchestrationEvent):
	"""Event emitted when a task fails."""

	event_type: str = 'task_failed'
	task_id: str
	agent_id: str
	error: str
	retry_count: int


class MessageSentEvent(OrchestrationEvent):
	"""Event emitted when a message is sent between agents."""

	event_type: str = 'message_sent'
	from_agent: str
	to_agent: str | None
	message_type: str
	message_id: str


class MessageReceivedEvent(OrchestrationEvent):
	"""Event emitted when an agent receives a message."""

	event_type: str = 'message_received'
	agent_id: str
	message_id: str
	from_agent: str


class DelegationRequestEvent(OrchestrationEvent):
	"""Event emitted when an agent requests to delegate a task."""

	event_type: str = 'delegation_request'
	from_agent: str
	to_agent: str | None
	task_description: str
	context: dict[str, Any] = Field(default_factory=dict)


class OrchestrationStartedEvent(OrchestrationEvent):
	"""Event emitted when orchestration session starts."""

	event_type: str = 'orchestration_started'
	session_id: str
	num_agents: int


class OrchestrationCompletedEvent(OrchestrationEvent):
	"""Event emitted when orchestration session completes."""

	event_type: str = 'orchestration_completed'
	session_id: str
	total_tasks: int
	completed_tasks: int
	failed_tasks: int
	total_time: float
