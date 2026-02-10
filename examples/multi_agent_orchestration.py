"""
Multi-Agent Orchestration Example

This example demonstrates how to use the orchestration layer to coordinate
multiple AI agents for complex web automation tasks.

The orchestration system allows you to:
1. Define multiple specialized agents with different roles
2. Configure LLM providers with proxy support
3. Assign and delegate tasks between agents
4. Monitor execution and collect results

Usage:
	python examples/multi_agent_orchestration.py
"""

import asyncio
import logging
from pathlib import Path

from browser_use.orchestration import (
	ConfigLoader,
	Orchestrator,
	TaskConfig,
	TaskPriority,
)

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


async def simple_example():
	"""Simple orchestration example with predefined tasks."""
	logger.info('=== Simple Multi-Agent Orchestration Example ===')

	# Load configuration from YAML
	config_path = Path(__file__).parent / 'orchestration_config.yaml'
	config = ConfigLoader.load_config(config_path)

	# Create orchestrator
	orchestrator = Orchestrator(config)
	await orchestrator.initialize()

	# Define tasks
	tasks = [
		TaskConfig(
			description='Navigate to https://example.com and extract the main heading',
			priority=TaskPriority.HIGH,
		),
		TaskConfig(
			description='Find and list all links on the page',
			priority=TaskPriority.MEDIUM,
		),
		TaskConfig(
			description='Take a screenshot of the page',
			priority=TaskPriority.LOW,
		),
	]

	try:
		# Run orchestration
		logger.info(f'Starting orchestration with {len(tasks)} tasks...')
		final_state = await orchestrator.run(tasks)

		# Print results
		logger.info('\n=== Orchestration Results ===')
		logger.info(f'Completed tasks: {len(final_state.completed_tasks)}')
		logger.info(f'Failed tasks: {len(final_state.failed_tasks)}')

		for result in final_state.results:
			logger.info(f'\nTask {result.task_id}:')
			logger.info(f'  Status: {result.status}')
			logger.info(f'  Agent: {result.agent_id}')
			logger.info(f'  Execution time: {result.execution_time:.2f}s')
			logger.info(f'  Steps taken: {result.steps_taken}')
			if result.error:
				logger.error(f'  Error: {result.error}')

	finally:
		# Cleanup
		await orchestrator.shutdown()


async def complex_example():
	"""Complex orchestration with task dependencies and role-based assignment."""
	logger.info('=== Complex Multi-Agent Orchestration Example ===')

	# Load configuration
	config_path = Path(__file__).parent / 'orchestration_config.yaml'
	config = ConfigLoader.load_config(config_path)

	# Create orchestrator
	orchestrator = Orchestrator(config)
	await orchestrator.initialize()

	# Define complex workflow with dependencies
	task1 = TaskConfig(
		description='Research the latest web automation frameworks and tools',
		priority=TaskPriority.HIGH,
		context={'search_query': 'web automation frameworks 2026', 'max_results': 5},
	)

	task2 = TaskConfig(
		description='Navigate to the top 3 framework websites and extract key features',
		priority=TaskPriority.HIGH,
		dependencies=[task1.id],  # Depends on research task
	)

	task3 = TaskConfig(
		description='Compare the extracted features and create a summary',
		priority=TaskPriority.MEDIUM,
		dependencies=[task2.id],  # Depends on navigation task
	)

	task4 = TaskConfig(
		description='Validate the summary for accuracy and completeness',
		priority=TaskPriority.HIGH,
		dependencies=[task3.id],  # Depends on summary task
	)

	tasks = [task1, task2, task3, task4]

	try:
		# Run orchestration
		logger.info(f'Starting complex orchestration with {len(tasks)} dependent tasks...')
		final_state = await orchestrator.run(tasks)

		# Print detailed results
		logger.info('\n=== Complex Orchestration Results ===')
		logger.info(f'Total time: {final_state.end_time - final_state.start_time:.2f}s')
		logger.info(f'Completed: {len(final_state.completed_tasks)}')
		logger.info(f'Failed: {len(final_state.failed_tasks)}')
		logger.info(f'Messages exchanged: {len(final_state.message_queue)}')

		# Print agent statistics
		agent_stats = orchestrator.agent_registry.get_all_stats()
		logger.info('\n=== Agent Statistics ===')
		for agent_stat in agent_stats['agents']:
			logger.info(f"\n{agent_stat['name']} ({agent_stat['role']}):")
			logger.info(f"  Status: {agent_stat['status']}")
			logger.info(f"  Tasks completed: {agent_stat['tasks_completed']}")
			logger.info(f"  Tasks failed: {agent_stat['tasks_failed']}")
			logger.info(f"  Total execution time: {agent_stat['total_execution_time']:.2f}s")

	finally:
		# Cleanup
		await orchestrator.shutdown()


async def event_driven_example():
	"""Example showing event-driven coordination with custom event handlers."""
	logger.info('=== Event-Driven Multi-Agent Orchestration Example ===')

	# Load configuration
	config_path = Path(__file__).parent / 'orchestration_config.yaml'
	config = ConfigLoader.load_config(config_path)

	# Create orchestrator
	orchestrator = Orchestrator(config)

	# Register custom event handlers
	@orchestrator.event_bus.on('task_started')
	async def on_task_started(event):
		logger.info(f'📋 Task started: {event.task_id} by agent {event.agent_id}')

	@orchestrator.event_bus.on('task_completed')
	async def on_task_completed(event):
		logger.info(
			f'✅ Task completed: {event.task_id} in {event.result.execution_time:.2f}s'
		)

	@orchestrator.event_bus.on('task_failed')
	async def on_task_failed(event):
		logger.error(f'❌ Task failed: {event.task_id} - {event.error}')

	@orchestrator.event_bus.on('agent_status_changed')
	async def on_status_changed(event):
		logger.debug(
			f'🤖 Agent {event.agent_id}: {event.old_status} → {event.new_status}'
		)

	await orchestrator.initialize()

	# Define tasks
	tasks = [
		TaskConfig(
			description='Navigate to https://github.com/browser-use/browser-use',
			priority=TaskPriority.HIGH,
		),
		TaskConfig(
			description='Extract the repository description and star count',
			priority=TaskPriority.HIGH,
		),
		TaskConfig(
			description='Find the documentation link and navigate to it',
			priority=TaskPriority.MEDIUM,
		),
	]

	try:
		# Run orchestration
		logger.info('Starting event-driven orchestration...')
		final_state = await orchestrator.run(tasks)

		# Print summary
		logger.info('\n=== Final Summary ===')
		stats = orchestrator.get_stats()
		logger.info(f"Session ID: {stats['session_id']}")
		logger.info(f"Total agents: {stats['agents']['total_agents']}")
		logger.info(f"Completed tasks: {stats['tasks']['completed']}")
		logger.info(f"Failed tasks: {stats['tasks']['failed']}")

	finally:
		await orchestrator.shutdown()


async def custom_agent_example():
	"""Example showing how to add custom agents programmatically."""
	logger.info('=== Custom Agent Configuration Example ===')

	from browser_use.orchestration import (
		AgentCapability,
		AgentConfig,
		AgentRole,
		LLMProviderConfig,
		LLMProviderType,
		OrchestrationConfig,
	)

	# Create configuration programmatically
	llm_provider = LLMProviderConfig(
		name='custom_vllm',
		provider_type=LLMProviderType.VLLM,
		model_name='Qwen3VL_32b',
		api_base='http://127.0.0.1:3333/v1',
		api_key='EMPTY',
		temperature=0.7,
	)

	# Create custom agent
	custom_agent = AgentConfig(
		name='custom_scraper',
		role=AgentRole.CUSTOM,
		description='Custom web scraping agent with specialized capabilities',
		llm_provider='custom_vllm',
		capabilities=[
			AgentCapability(
				name='price_extraction',
				description='Extract product prices from e-commerce sites',
				parameters={'currency_formats': ['USD', 'EUR', 'GBP']},
			),
			AgentCapability(
				name='review_analysis',
				description='Analyze product reviews and ratings',
			),
		],
		system_prompt='You are a specialized web scraping agent focused on e-commerce data extraction.',
		max_steps=150,
	)

	# Create orchestration config
	config = OrchestrationConfig(
		llm_providers=[llm_provider],
		agents=[custom_agent],
		max_concurrent_agents=1,
		shared_browser=True,
	)

	# Create and run orchestrator
	orchestrator = Orchestrator(config)
	await orchestrator.initialize()

	tasks = [
		TaskConfig(
			description='Extract product information from an e-commerce page',
			context={'url': 'https://example.com/products'},
		),
	]

	try:
		final_state = await orchestrator.run(tasks)
		logger.info(f'Custom agent completed {len(final_state.completed_tasks)} tasks')

	finally:
		await orchestrator.shutdown()


def main():
	"""Main entry point."""
	import sys

	if len(sys.argv) > 1:
		example_type = sys.argv[1]
	else:
		example_type = 'simple'

	examples = {
		'simple': simple_example,
		'complex': complex_example,
		'events': event_driven_example,
		'custom': custom_agent_example,
	}

	if example_type not in examples:
		print(f'Unknown example type: {example_type}')
		print(f'Available examples: {", ".join(examples.keys())}')
		sys.exit(1)

	logger.info(f'Running {example_type} example...')
	asyncio.run(examples[example_type]())


if __name__ == '__main__':
	main()
