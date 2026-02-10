"""Agent registry and role management for orchestration system."""

import asyncio
import logging
import time
from typing import Any

from bubus import EventBus

from browser_use.agent.service import Agent
from browser_use.agent.views import AgentSettings
from browser_use.browser.session import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.orchestration.events import AgentRegisteredEvent, AgentStatusChangedEvent
from browser_use.orchestration.views import AgentConfig, AgentRole, AgentStatus

logger = logging.getLogger(__name__)


class ManagedAgent:
	"""Wrapper for an agent instance with orchestration metadata."""

	def __init__(
		self,
		agent_id: str,
		config: AgentConfig,
		llm: BaseChatModel,
		browser_session: BrowserSession | None = None,
	):
		self.id = agent_id
		self.config = config
		self.llm = llm
		self.browser_session = browser_session
		self.status = AgentStatus.IDLE
		self.current_task_id: str | None = None
		self.last_activity: float = time.time()

		# Create browser-use Agent
		# Note: task will be set when executing, max_failures from config
		self.agent = Agent(
			task='',  # Task will be set when executing
			llm=llm,
			browser_session=browser_session,
			max_failures=config.max_retry_attempts,
		)

		# Statistics
		self.tasks_completed = 0
		self.tasks_failed = 0
		self.total_execution_time = 0.0

	def __repr__(self) -> str:
		return (
			f'ManagedAgent(id={self.id}, name={self.config.name}, '
			f'role={self.config.role}, status={self.status})'
		)


class AgentRegistry:
	"""Registry for managing multiple agents in the orchestration system."""

	def __init__(self, event_bus: EventBus | None = None):
		self._agents: dict[str, ManagedAgent] = {}
		self._agents_by_role: dict[AgentRole, list[str]] = {}
		self._event_bus = event_bus or EventBus()
		self._lock = asyncio.Lock()

	async def register_agent(
		self,
		config: AgentConfig,
		llm: BaseChatModel,
		browser_session: BrowserSession | None = None,
	) -> ManagedAgent:
		"""Register a new agent in the registry.

		Args:
			config: Agent configuration
			llm: LLM provider for the agent
			browser_session: Optional browser session (if None, agent creates its own)

		Returns:
			ManagedAgent instance

		Raises:
			ValueError: If agent with same ID already exists
		"""
		async with self._lock:
			if config.id in self._agents:
				raise ValueError(f'Agent with ID {config.id} already registered')

			# Create managed agent
			managed_agent = ManagedAgent(
				agent_id=config.id, config=config, llm=llm, browser_session=browser_session
			)

			# Register in main dict
			self._agents[config.id] = managed_agent

			# Register by role
			if config.role not in self._agents_by_role:
				self._agents_by_role[config.role] = []
			self._agents_by_role[config.role].append(config.id)

			# Emit registration event
			await self._event_bus.emit(  # type: ignore
				AgentRegisteredEvent(
					timestamp=time.time(),
					agent_id=config.id,
					agent_name=config.name,
					role=config.role.value,
				)
			)

			logger.info(f'Registered agent: {config.name} (ID: {config.id}, role: {config.role})')
			return managed_agent

	async def unregister_agent(self, agent_id: str) -> None:
		"""Unregister an agent from the registry.

		Args:
			agent_id: Agent ID to unregister
		"""
		async with self._lock:
			if agent_id not in self._agents:
				logger.warning(f'Attempted to unregister unknown agent: {agent_id}')
				return

			agent = self._agents[agent_id]

			# Remove from role mapping
			if agent.config.role in self._agents_by_role:
				self._agents_by_role[agent.config.role].remove(agent_id)
				if not self._agents_by_role[agent.config.role]:
					del self._agents_by_role[agent.config.role]

			# Remove from main dict
			del self._agents[agent_id]

			logger.info(f'Unregistered agent: {agent.config.name} (ID: {agent_id})')

	def get_agent(self, agent_id: str) -> ManagedAgent:
		"""Get agent by ID.

		Args:
			agent_id: Agent ID

		Returns:
			ManagedAgent instance

		Raises:
			KeyError: If agent not found
		"""
		if agent_id not in self._agents:
			raise KeyError(f'Agent not found: {agent_id}. Available: {list(self._agents.keys())}')
		return self._agents[agent_id]

	def get_agent_by_name(self, agent_name: str) -> ManagedAgent:
		"""Get agent by name.

		Args:
			agent_name: Agent name

		Returns:
			ManagedAgent instance

		Raises:
			KeyError: If agent not found
		"""
		for agent in self._agents.values():
			if agent.config.name == agent_name:
				return agent
		available = [agent.config.name for agent in self._agents.values()]
		raise KeyError(f'Agent not found: {agent_name}. Available: {available}')

	def get_agents_by_role(self, role: AgentRole) -> list[ManagedAgent]:
		"""Get all agents with a specific role.

		Args:
			role: Agent role to filter by

		Returns:
			List of ManagedAgent instances
		"""
		agent_ids = self._agents_by_role.get(role, [])
		return [self._agents[aid] for aid in agent_ids]

	def get_available_agent(self, role: AgentRole | None = None) -> ManagedAgent | None:
		"""Get an available (idle) agent, optionally filtered by role.

		Args:
			role: Optional role to filter by

		Returns:
			ManagedAgent instance or None if no available agent
		"""
		candidates = (
			self.get_agents_by_role(role) if role else list(self._agents.values())
		)

		for agent in candidates:
			if agent.status == AgentStatus.IDLE:
				return agent

		return None

	async def update_agent_status(
		self, agent_id: str, new_status: AgentStatus, task_id: str | None = None
	) -> None:
		"""Update agent status and emit event.

		Args:
			agent_id: Agent ID
			new_status: New status
			task_id: Optional task ID associated with status change
		"""
		async with self._lock:
			agent = self.get_agent(agent_id)
			old_status = agent.status

			agent.status = new_status
			agent.last_activity = time.time()

			if task_id:
				agent.current_task_id = task_id

			# Emit status change event
			await self._event_bus.emit(  # type: ignore
				AgentStatusChangedEvent(
					timestamp=time.time(),
					agent_id=agent_id,
					old_status=old_status,
					new_status=new_status,
					metadata={'task_id': task_id} if task_id else {},
				)
			)

			logger.debug(f'Agent {agent.config.name} status: {old_status} -> {new_status}')

	def list_agents(self) -> list[ManagedAgent]:
		"""List all registered agents.

		Returns:
			List of ManagedAgent instances
		"""
		return list(self._agents.values())

	def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
		"""Get statistics for an agent.

		Args:
			agent_id: Agent ID

		Returns:
			Dictionary with agent statistics
		"""
		agent = self.get_agent(agent_id)
		return {
			'id': agent.id,
			'name': agent.config.name,
			'role': agent.config.role.value,
			'status': agent.status.value,
			'current_task': agent.current_task_id,
			'tasks_completed': agent.tasks_completed,
			'tasks_failed': agent.tasks_failed,
			'total_execution_time': agent.total_execution_time,
			'last_activity': agent.last_activity,
		}

	def get_all_stats(self) -> dict[str, Any]:
		"""Get statistics for all agents.

		Returns:
			Dictionary with overall statistics
		"""
		agents_stats = [self.get_agent_stats(aid) for aid in self._agents.keys()]

		return {
			'total_agents': len(self._agents),
			'agents_by_status': {
				status.value: sum(1 for a in self._agents.values() if a.status == status)
				for status in AgentStatus
			},
			'agents_by_role': {
				role.value: len(agent_ids)
				for role, agent_ids in self._agents_by_role.items()
			},
			'agents': agents_stats,
		}

	async def shutdown_all(self) -> None:
		"""Shutdown all agents and clean up resources."""
		async with self._lock:
			for agent in self._agents.values():
				if agent.browser_session:
					try:
						await agent.browser_session.close()  # type: ignore
					except Exception as e:
						logger.error(f'Error closing browser for agent {agent.id}: {e}')

			self._agents.clear()
			self._agents_by_role.clear()

		logger.info('Shutdown all agents')
