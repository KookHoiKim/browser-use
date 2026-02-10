"""Core orchestration service for multi-agent coordination."""

import asyncio
import logging
import time
from collections import deque
from typing import Any

from bubus import EventBus

from browser_use.agent.views import AgentHistoryList
from browser_use.browser import Browser
from browser_use.browser.session import BrowserSession
from browser_use.orchestration.agent_registry import AgentRegistry, ManagedAgent
from browser_use.orchestration.events import (
	MessageReceivedEvent,
	MessageSentEvent,
	OrchestrationCompletedEvent,
	OrchestrationStartedEvent,
	TaskAssignedEvent,
	TaskCompletedEvent,
	TaskFailedEvent,
	TaskStartedEvent,
)
from browser_use.orchestration.llm_provider import LLMProviderRegistry
from browser_use.orchestration.views import (
	AgentConfig,
	AgentMessage,
	AgentStatus,
	OrchestrationConfig,
	OrchestrationState,
	TaskConfig,
	TaskResult,
)

logger = logging.getLogger(__name__)


class Orchestrator:
	"""Multi-agent orchestration service.

	Manages task assignment, agent coordination, and inter-agent communication
	for web-based automation tasks.
	"""

	def __init__(self, config: OrchestrationConfig, event_bus: EventBus | None = None):
		"""Initialize orchestrator.

		Args:
			config: Orchestration configuration
			event_bus: Optional event bus for event-driven coordination
		"""
		self.config = config
		self.event_bus = event_bus or EventBus()

		# Initialize registries
		self.llm_registry = LLMProviderRegistry()
		self.agent_registry = AgentRegistry(event_bus=self.event_bus)

		# State management
		self.state = OrchestrationState()
		self.task_queue: deque[TaskConfig] = deque()
		self.active_tasks: dict[str, TaskConfig] = {}

		# Message passing
		self.message_handlers: dict[str, list[asyncio.Queue[AgentMessage]]] = {}

		# Browser management
		self.browser: Browser | None = None
		self.shared_browser_session: BrowserSession | None = None

		# Execution control
		self._running = False
		self._worker_tasks: list[asyncio.Task[Any]] = []

	async def initialize(self) -> None:
		"""Initialize orchestrator: load LLM providers, register agents, and set up browser."""
		logger.info('Initializing orchestrator...')

		# Register LLM providers
		for provider_config in self.config.llm_providers:
			self.llm_registry.register(provider_config)
		logger.info(f'Registered {len(self.config.llm_providers)} LLM providers')

		# Initialize browser if shared mode
		if self.config.shared_browser:
			self.browser = Browser()
			assert self.browser is not None
			self.shared_browser_session = await self.browser.new_session()
			logger.info('Created shared browser session')

		# Register agents
		for agent_config in self.config.agents:
			await self._register_agent(agent_config)
		logger.info(f'Registered {len(self.config.agents)} agents')

		# Set coordinator
		if not self.config.coordinator_agent and self.config.agents:
			self.config.coordinator_agent = self.config.agents[0].id
			logger.info(f'Set default coordinator: {self.config.agents[0].name}')

		logger.info('Orchestrator initialized successfully')

	async def _register_agent(self, agent_config: AgentConfig) -> ManagedAgent:
		"""Register an agent with its LLM provider.

		Args:
			agent_config: Agent configuration

		Returns:
			Registered ManagedAgent instance
		"""
		# Get LLM provider
		llm = self.llm_registry.get(agent_config.llm_provider)

		# Get or create browser session
		browser_session = None
		if self.config.shared_browser:
			browser_session = self.shared_browser_session
		else:
			# Each agent gets its own browser
			browser = Browser()
			browser_session = await browser.new_session()

		# Register agent
		managed_agent = await self.agent_registry.register_agent(
			config=agent_config, llm=llm, browser_session=browser_session
		)

		# Initialize message queue for agent
		self.message_handlers[agent_config.id] = [asyncio.Queue()]

		# Update state
		self.state.active_agents[agent_config.id] = AgentStatus.IDLE

		return managed_agent

	async def add_task(self, task: TaskConfig) -> None:
		"""Add a task to the orchestration queue.

		Args:
			task: Task configuration
		"""
		self.task_queue.append(task)
		self.state.pending_tasks.append(task.id)
		logger.info(f'Added task: {task.description} (ID: {task.id})')

	async def _assign_task(self, task: TaskConfig) -> ManagedAgent | None:
		"""Assign a task to an appropriate agent.

		Args:
			task: Task to assign

		Returns:
			ManagedAgent that accepted the task, or None if no agent available
		"""
		# Check if task has assigned agent
		if task.assigned_agent:
			try:
				agent = self.agent_registry.get_agent(task.assigned_agent)
				if agent.status == AgentStatus.IDLE:
					return agent
				else:
					logger.warning(
						f'Assigned agent {task.assigned_agent} is busy, looking for alternative'
					)
			except KeyError:
				logger.error(f'Assigned agent {task.assigned_agent} not found')

		# Find available agent (simple round-robin for now)
		agent = self.agent_registry.get_available_agent()
		if not agent:
			logger.debug('No available agents for task assignment')
			return None

		return agent

	async def _execute_task(self, task: TaskConfig, agent: ManagedAgent) -> TaskResult:
		"""Execute a task with an agent.

		Args:
			task: Task to execute
			agent: Agent to execute the task

		Returns:
			TaskResult with execution outcome
		"""
		start_time = time.time()

		try:
			# Update agent status
			await self.agent_registry.update_agent_status(
				agent.id, AgentStatus.ACTING, task_id=task.id
			)

			# Emit task started event
			await self.event_bus.emit(  # type: ignore
				TaskStartedEvent(
					timestamp=time.time(), task_id=task.id, agent_id=agent.id
				)
			)

			# Set agent task
			agent.agent.task = task.description

			# Build context for agent
			if task.context:
				context_str = '\n'.join(
					f'{key}: {value}' for key, value in task.context.items()
				)
				agent.agent.task = f'{task.description}\n\nContext:\n{context_str}'

			# Execute agent
			result: AgentHistoryList = await agent.agent.run()

			# Update agent statistics
			execution_time = time.time() - start_time
			agent.tasks_completed += 1
			agent.total_execution_time += execution_time

			# Create task result
			# Check if any history items contain errors
			has_error = any(
				h.result and any(r.error for r in h.result) for h in result.history
			)

			task_result = TaskResult(
				task_id=task.id,
				agent_id=agent.id,
				status='success' if not has_error else 'partial',
				output={
					'result': str(result),
					'steps_taken': len(result),
					'success': not has_error,
				},
				execution_time=execution_time,
				steps_taken=len(result),
				metadata={
					'agent_name': agent.config.name,
					'agent_role': agent.config.role.value,
				},
			)

			logger.info(
				f'Task {task.id} completed by {agent.config.name} in {execution_time:.2f}s'
			)

			return task_result

		except Exception as e:
			execution_time = time.time() - start_time
			agent.tasks_failed += 1

			logger.error(f'Task {task.id} failed: {e}', exc_info=True)

			return TaskResult(
				task_id=task.id,
				agent_id=agent.id,
				status='failure',
				error=str(e),
				execution_time=execution_time,
				steps_taken=0,
				metadata={'agent_name': agent.config.name},
			)

		finally:
			# Reset agent status
			await self.agent_registry.update_agent_status(agent.id, AgentStatus.IDLE)
			agent.current_task_id = None

	async def _task_worker(self) -> None:
		"""Worker coroutine that processes tasks from the queue."""
		while self._running:
			try:
				# Check if we can process more tasks
				active_count = sum(
					1
					for status in self.state.active_agents.values()
					if status != AgentStatus.IDLE
				)

				if active_count >= self.config.max_concurrent_agents:
					await asyncio.sleep(0.5)
					continue

				# Get next task
				if not self.task_queue:
					await asyncio.sleep(0.5)
					continue

				task = self.task_queue.popleft()

				# Check dependencies
				if task.dependencies:
					dependencies_met = all(
						dep_id in self.state.completed_tasks
						for dep_id in task.dependencies
					)
					if not dependencies_met:
						# Re-queue task
						self.task_queue.append(task)
						await asyncio.sleep(0.5)
						continue

				# Assign task
				agent = await self._assign_task(task)
				if not agent:
					# Re-queue task
					self.task_queue.append(task)
					await asyncio.sleep(1.0)
					continue

				# Move task to active
				self.active_tasks[task.id] = task
				self.state.pending_tasks.remove(task.id)

				# Emit assignment event
				await self.event_bus.emit(  # type: ignore
					TaskAssignedEvent(
						timestamp=time.time(),
						task_id=task.id,
						agent_id=agent.id,
						task_description=task.description,
					)
				)

				# Execute task (non-blocking)
				asyncio.create_task(self._execute_and_handle_result(task, agent))

			except Exception as e:
				logger.error(f'Error in task worker: {e}', exc_info=True)
				await asyncio.sleep(1.0)

	async def _execute_and_handle_result(
		self, task: TaskConfig, agent: ManagedAgent
	) -> None:
		"""Execute task and handle result.

		Args:
			task: Task to execute
			agent: Agent to execute with
		"""
		try:
			result = await self._execute_task(task, agent)

			# Remove from active tasks
			if task.id in self.active_tasks:
				del self.active_tasks[task.id]

			# Update state
			self.state.results.append(result)

			if result.status == 'success':
				self.state.completed_tasks.append(task.id)

				# Emit completion event
				await self.event_bus.emit(  # type: ignore
					TaskCompletedEvent(
						timestamp=time.time(),
						task_id=task.id,
						agent_id=agent.id,
						result=result,
					)
				)
			else:
				# Handle failure and retry logic
				if task.max_retries > 0:
					task.max_retries -= 1
					logger.info(f'Retrying task {task.id} ({task.max_retries} retries left)')
					await asyncio.sleep(self.config.task_retry_delay)
					await self.add_task(task)

					# Emit failure event
					await self.event_bus.emit(  # type: ignore
						TaskFailedEvent(
							timestamp=time.time(),
							task_id=task.id,
							agent_id=agent.id,
							error=result.error or 'Unknown error',
							retry_count=task.max_retries,
						)
					)
				else:
					self.state.failed_tasks.append(task.id)
					logger.error(f'Task {task.id} failed after all retries')

					# Emit final failure event
					await self.event_bus.emit(  # type: ignore
						TaskFailedEvent(
							timestamp=time.time(),
							task_id=task.id,
							agent_id=agent.id,
							error=result.error or 'Unknown error',
							retry_count=0,
						)
					)

		except Exception as e:
			logger.error(f'Error handling task result: {e}', exc_info=True)

	async def send_message(self, message: AgentMessage) -> None:
		"""Send a message between agents.

		Args:
			message: Message to send
		"""
		# Emit message sent event
		await self.event_bus.emit(  # type: ignore
			MessageSentEvent(
				timestamp=time.time(),
				from_agent=message.from_agent,
				to_agent=message.to_agent,
				message_type=message.message_type,
				message_id=message.id,
			)
		)

		# Deliver message
		if message.to_agent:
			# Direct message
			if message.to_agent in self.message_handlers:
				for queue in self.message_handlers[message.to_agent]:
					await queue.put(message)

				await self.event_bus.emit(  # type: ignore
					MessageReceivedEvent(
						timestamp=time.time(),
						agent_id=message.to_agent,
						message_id=message.id,
						from_agent=message.from_agent,
					)
				)
		else:
			# Broadcast message
			for agent_id, queues in self.message_handlers.items():
				if agent_id != message.from_agent:
					for queue in queues:
						await queue.put(message)

					await self.event_bus.emit(  # type: ignore
						MessageReceivedEvent(
							timestamp=time.time(),
							agent_id=agent_id,
							message_id=message.id,
							from_agent=message.from_agent,
						)
					)

		self.state.message_queue.append(message)

	async def run(self, tasks: list[TaskConfig] | None = None) -> OrchestrationState:
		"""Run the orchestration system.

		Args:
			tasks: Optional list of tasks to execute

		Returns:
			Final orchestration state
		"""
		logger.info('Starting orchestration...')
		self._running = True
		self.state.start_time = time.time()

		# Emit orchestration started event
		await self.event_bus.emit(  # type: ignore
			OrchestrationStartedEvent(
				timestamp=time.time(),
				session_id=self.state.session_id,
				num_agents=len(self.config.agents),
			)
		)

		# Add tasks to queue
		if tasks:
			for task in tasks:
				await self.add_task(task)

		# Start worker tasks
		num_workers = min(self.config.max_concurrent_agents, 3)
		for _ in range(num_workers):
			worker = asyncio.create_task(self._task_worker())
			self._worker_tasks.append(worker)

		logger.info(f'Started {num_workers} task workers')

		# Wait for all tasks to complete
		try:
			while self._running:
				# Check if all tasks are done
				if not self.task_queue and not self.active_tasks:
					logger.info('All tasks completed, stopping orchestration')
					break

				await asyncio.sleep(1.0)

		except KeyboardInterrupt:
			logger.info('Orchestration interrupted by user')

		finally:
			await self.stop()

		return self.state

	async def stop(self) -> None:
		"""Stop the orchestration system."""
		logger.info('Stopping orchestration...')
		self._running = False

		# Cancel worker tasks
		for task in self._worker_tasks:
			task.cancel()

		await asyncio.gather(*self._worker_tasks, return_exceptions=True)
		self._worker_tasks.clear()

		# Update state
		self.state.end_time = time.time()

		# Emit orchestration completed event
		total_time = self.state.end_time - (self.state.start_time or self.state.end_time)
		await self.event_bus.emit(  # type: ignore
			OrchestrationCompletedEvent(
				timestamp=time.time(),
				session_id=self.state.session_id,
				total_tasks=len(self.state.completed_tasks) + len(self.state.failed_tasks),
				completed_tasks=len(self.state.completed_tasks),
				failed_tasks=len(self.state.failed_tasks),
				total_time=total_time,
			)
		)

		logger.info(
			f'Orchestration stopped. Completed: {len(self.state.completed_tasks)}, '
			f'Failed: {len(self.state.failed_tasks)}'
		)

	async def shutdown(self) -> None:
		"""Shutdown orchestrator and clean up all resources."""
		logger.info('Shutting down orchestrator...')

		await self.stop()

		# Shutdown all agents
		await self.agent_registry.shutdown_all()

		# Close shared browser if exists
		if self.shared_browser_session:
			await self.shared_browser_session.close()  # type: ignore

		if self.browser:
			await self.browser.close()

		logger.info('Orchestrator shutdown complete')

	def get_stats(self) -> dict[str, Any]:
		"""Get orchestration statistics.

		Returns:
			Dictionary with statistics
		"""
		return {
			'session_id': self.state.session_id,
			'status': 'running' if self._running else 'stopped',
			'start_time': self.state.start_time,
			'end_time': self.state.end_time,
			'tasks': {
				'pending': len(self.state.pending_tasks),
				'active': len(self.active_tasks),
				'completed': len(self.state.completed_tasks),
				'failed': len(self.state.failed_tasks),
			},
			'agents': self.agent_registry.get_all_stats(),
			'messages': len(self.state.message_queue),
		}
