"""Tests for multi-agent orchestration system."""

import asyncio
import tempfile
from pathlib import Path

import pytest
import yaml

from browser_use.orchestration import (
	AgentCapability,
	AgentConfig,
	AgentRole,
	AgentStatus,
	ConfigLoader,
	LLMProviderConfig,
	LLMProviderType,
	LLMProviderRegistry,
	ManagedAgent,
	OrchestrationConfig,
	Orchestrator,
	ProxyConfig,
	TaskConfig,
	TaskPriority,
)


@pytest.fixture
def minimal_config():
	"""Create minimal orchestration configuration for testing."""
	llm_provider = LLMProviderConfig(
		name='test_provider',
		provider_type=LLMProviderType.OPENAI,
		model_name='gpt-4o-mini',
		temperature=0.7,
	)

	agent = AgentConfig(
		name='test_agent',
		role=AgentRole.NAVIGATOR,
		description='Test agent for unit tests',
		llm_provider='test_provider',
		max_steps=10,
	)

	return OrchestrationConfig(
		llm_providers=[llm_provider],
		agents=[agent],
		max_concurrent_agents=1,
		shared_browser=True,
	)


@pytest.fixture
def multi_agent_config():
	"""Create multi-agent configuration for testing."""
	llm_provider = LLMProviderConfig(
		name='test_provider',
		provider_type=LLMProviderType.OPENAI,
		model_name='gpt-4o-mini',
		temperature=0.7,
	)

	coordinator = AgentConfig(
		name='coordinator',
		role=AgentRole.COORDINATOR,
		description='Coordinator agent',
		llm_provider='test_provider',
		max_steps=10,
		can_delegate=True,
		delegation_roles=[AgentRole.NAVIGATOR, AgentRole.RESEARCHER],
	)

	navigator = AgentConfig(
		name='navigator',
		role=AgentRole.NAVIGATOR,
		description='Navigator agent',
		llm_provider='test_provider',
		max_steps=20,
	)

	researcher = AgentConfig(
		name='researcher',
		role=AgentRole.RESEARCHER,
		description='Researcher agent',
		llm_provider='test_provider',
		max_steps=20,
	)

	return OrchestrationConfig(
		llm_providers=[llm_provider],
		agents=[coordinator, navigator, researcher],
		max_concurrent_agents=2,
		coordinator_agent=coordinator.id,
		shared_browser=False,
	)


class TestProxyConfig:
	"""Tests for ProxyConfig model."""

	def test_proxy_config_creation(self):
		"""Test creating proxy configuration."""
		proxy = ProxyConfig(
			enabled=True, http_proxy='http://127.0.0.1:9090', https_proxy='http://127.0.0.1:9090'
		)

		assert proxy.enabled
		assert proxy.http_proxy == 'http://127.0.0.1:9090'
		assert proxy.https_proxy == 'http://127.0.0.1:9090'

	def test_proxy_config_validation(self):
		"""Test proxy URL validation."""
		with pytest.raises(ValueError):
			ProxyConfig(enabled=True, http_proxy='invalid-proxy')

	def test_proxy_config_disabled(self):
		"""Test disabled proxy configuration."""
		proxy = ProxyConfig(enabled=False)
		assert not proxy.enabled
		assert proxy.http_proxy is None


class TestLLMProviderConfig:
	"""Tests for LLMProviderConfig model."""

	def test_openai_provider_config(self):
		"""Test OpenAI provider configuration."""
		config = LLMProviderConfig(
			name='openai_test',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o',
			api_key='test-key',
			temperature=0.7,
			max_tokens=4096,
		)

		assert config.name == 'openai_test'
		assert config.provider_type == LLMProviderType.OPENAI
		assert config.model_name == 'gpt-4o'
		assert config.temperature == 0.7

	def test_azure_provider_config(self):
		"""Test Azure provider configuration with proxy."""
		config = LLMProviderConfig(
			name='azure_test',
			provider_type=LLMProviderType.AZURE,
			model_name='gpt-4',
			azure_deployment='test-deployment',
			api_key='test-key',
			api_base='https://test.openai.azure.com',
			api_version='2024-02-15-preview',
			proxy=ProxyConfig(
				enabled=True, http_proxy='http://127.0.0.1:9090', https_proxy='http://127.0.0.1:9090'
			),
		)

		assert config.provider_type == LLMProviderType.AZURE
		assert config.azure_deployment == 'test-deployment'
		assert config.proxy.enabled

	def test_vllm_provider_config(self):
		"""Test vLLM provider configuration."""
		config = LLMProviderConfig(
			name='vllm_test',
			provider_type=LLMProviderType.VLLM,
			model_name='Qwen3VL_32b',
			api_base='http://127.0.0.1:3333/v1',
			api_key='EMPTY',
		)

		assert config.provider_type == LLMProviderType.VLLM
		assert config.api_base == 'http://127.0.0.1:3333/v1'


class TestAgentConfig:
	"""Tests for AgentConfig model."""

	def test_agent_config_creation(self):
		"""Test creating agent configuration."""
		agent = AgentConfig(
			name='test_agent',
			role=AgentRole.NAVIGATOR,
			description='Test agent',
			llm_provider='test_provider',
			max_steps=100,
		)

		assert agent.name == 'test_agent'
		assert agent.role == AgentRole.NAVIGATOR
		assert agent.max_steps == 100
		assert agent.can_delegate
		assert agent.can_receive_delegations

	def test_agent_with_capabilities(self):
		"""Test agent with custom capabilities."""
		capabilities = [
			AgentCapability(
				name='scraping', description='Web scraping', parameters={'timeout': 30}
			),
			AgentCapability(name='parsing', description='Data parsing'),
		]

		agent = AgentConfig(
			name='scraper',
			role=AgentRole.DATA_EXTRACTOR,
			description='Scraper agent',
			llm_provider='test_provider',
			capabilities=capabilities,
		)

		assert len(agent.capabilities) == 2
		assert agent.capabilities[0].name == 'scraping'
		assert agent.capabilities[0].parameters['timeout'] == 30

	def test_agent_delegation_config(self):
		"""Test agent delegation configuration."""
		agent = AgentConfig(
			name='coordinator',
			role=AgentRole.COORDINATOR,
			description='Coordinator',
			llm_provider='test_provider',
			can_delegate=True,
			delegation_roles=[AgentRole.NAVIGATOR, AgentRole.RESEARCHER],
		)

		assert agent.can_delegate
		assert AgentRole.NAVIGATOR in agent.delegation_roles
		assert AgentRole.RESEARCHER in agent.delegation_roles


class TestOrchestrationConfig:
	"""Tests for OrchestrationConfig model."""

	def test_config_validation_unique_providers(self):
		"""Test that LLM provider names must be unique."""
		provider1 = LLMProviderConfig(
			name='duplicate',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o',
		)
		provider2 = LLMProviderConfig(
			name='duplicate',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o-mini',
		)

		agent = AgentConfig(
			name='agent', role=AgentRole.NAVIGATOR, description='Test', llm_provider='duplicate'
		)

		with pytest.raises(ValueError, match='provider names must be unique'):
			OrchestrationConfig(
				llm_providers=[provider1, provider2],
				agents=[agent],
			)

	def test_config_validation_unique_agents(self):
		"""Test that agent names must be unique."""
		provider = LLMProviderConfig(
			name='provider',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o',
		)

		agent1 = AgentConfig(
			name='duplicate', role=AgentRole.NAVIGATOR, description='Test', llm_provider='provider'
		)
		agent2 = AgentConfig(
			name='duplicate', role=AgentRole.RESEARCHER, description='Test', llm_provider='provider'
		)

		with pytest.raises(ValueError, match='Agent names must be unique'):
			OrchestrationConfig(
				llm_providers=[provider],
				agents=[agent1, agent2],
			)

	def test_sequence_validation_unknown_agent(self):
		"""Test that sequence steps must reference known agents."""
		provider = LLMProviderConfig(
			name='provider',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o',
		)

		agent = AgentConfig(
			name='navigator',
			role=AgentRole.NAVIGATOR,
			description='Test',
			llm_provider='provider',
		)

		with pytest.raises(ValueError, match='Sequence steps reference unknown agents'):
			OrchestrationConfig(
				llm_providers=[provider],
				agents=[agent],
				sequence={'enabled': True, 'steps': ['missing_agent']},
			)

	def test_sequence_auto_enable(self):
		"""Test that providing steps auto-enables sequence mode."""
		provider = LLMProviderConfig(
			name='provider',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o',
		)

		agent = AgentConfig(
			name='navigator',
			role=AgentRole.NAVIGATOR,
			description='Test',
			llm_provider='provider',
		)

		config = OrchestrationConfig(
			llm_providers=[provider],
			agents=[agent],
			sequence={'steps': ['navigator']},
		)

		assert config.sequence.enabled


class TestConfigLoader:
	"""Tests for ConfigLoader."""

	def test_load_yaml_file(self):
		"""Test loading YAML configuration file."""
		config_data = {
			'llm_providers': [
				{
					'name': 'test_provider',
					'provider_type': 'openai',
					'model_name': 'gpt-4o-mini',
					'temperature': 0.7,
				}
			],
			'agents': [
				{
					'name': 'test_agent',
					'role': 'navigator',
					'description': 'Test agent',
					'llm_provider': 'test_provider',
				}
			],
		}

		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			yaml.dump(config_data, f)
			temp_path = f.name

		try:
			config = ConfigLoader.load_config(temp_path)
			assert len(config.llm_providers) == 1
			assert len(config.agents) == 1
			assert config.agents[0].name == 'test_agent'
		finally:
			Path(temp_path).unlink()

	def test_load_yaml_with_env_vars(self):
		"""Test loading YAML with environment variable substitution."""
		import os

		os.environ['TEST_API_KEY'] = 'secret-key-123'
		os.environ['TEST_MODEL'] = 'gpt-4o'

		config_data = {
			'llm_providers': [
				{
					'name': 'test_provider',
					'provider_type': 'openai',
					'model_name': '${TEST_MODEL}',
					'api_key': '${TEST_API_KEY}',
					'temperature': 0.7,
				}
			],
			'agents': [
				{
					'name': 'test_agent',
					'role': 'navigator',
					'description': 'Test agent',
					'llm_provider': 'test_provider',
				}
			],
		}

		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			yaml.dump(config_data, f)
			temp_path = f.name

		try:
			config = ConfigLoader.load_config(temp_path)
			assert config.llm_providers[0].api_key == 'secret-key-123'
			assert config.llm_providers[0].model_name == 'gpt-4o'
		finally:
			Path(temp_path).unlink()
			del os.environ['TEST_API_KEY']
			del os.environ['TEST_MODEL']


class TestLLMProviderRegistry:
	"""Tests for LLMProviderRegistry."""

	def test_register_provider(self):
		"""Test registering an LLM provider."""
		registry = LLMProviderRegistry()

		config = LLMProviderConfig(
			name='test_provider',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o-mini',
		)

		registry.register(config)
		assert 'test_provider' in registry.list_providers()

	def test_get_provider(self):
		"""Test retrieving a registered provider."""
		registry = LLMProviderRegistry()

		config = LLMProviderConfig(
			name='test_provider',
			provider_type=LLMProviderType.OPENAI,
			model_name='gpt-4o-mini',
		)

		registry.register(config)
		provider = registry.get('test_provider')
		assert provider is not None
		assert provider.model == 'gpt-4o-mini'

	def test_get_nonexistent_provider(self):
		"""Test getting a non-existent provider raises error."""
		registry = LLMProviderRegistry()

		with pytest.raises(KeyError):
			registry.get('nonexistent')


class TestTaskConfig:
	"""Tests for TaskConfig model."""

	def test_task_config_creation(self):
		"""Test creating task configuration."""
		task = TaskConfig(
			description='Test task',
			priority=TaskPriority.HIGH,
			context={'key': 'value'},
		)

		assert task.description == 'Test task'
		assert task.priority == TaskPriority.HIGH
		assert task.context['key'] == 'value'
		assert task.id is not None

	def test_task_with_dependencies(self):
		"""Test task with dependencies."""
		task1 = TaskConfig(description='Task 1')
		task2 = TaskConfig(description='Task 2', dependencies=[task1.id])

		assert task1.id in task2.dependencies


async def test_orchestrator_initialization(minimal_config):
	"""Test orchestrator initialization."""
	orchestrator = Orchestrator(minimal_config)
	await orchestrator.initialize()

	try:
		assert len(orchestrator.llm_registry.list_providers()) == 1
		assert len(orchestrator.agent_registry.list_agents()) == 1

		agents = orchestrator.agent_registry.list_agents()
		assert agents[0].config.name == 'test_agent'
	finally:
		await orchestrator.shutdown()


async def test_orchestrator_task_execution(minimal_config, mock_llm_simple):
	"""Test basic task execution with orchestrator."""
	# Override the LLM provider config to use mock
	minimal_config.llm_providers[0].provider_type = LLMProviderType.OPENAI
	minimal_config.llm_providers[0].model_name = 'gpt-4o-mini'

	orchestrator = Orchestrator(minimal_config)

	# Replace LLM with mock before initialization
	orchestrator.llm_registry.register(minimal_config.llm_providers[0])
	orchestrator.llm_registry._providers['test_provider'] = mock_llm_simple

	await orchestrator.initialize()

	task = TaskConfig(description='Navigate to https://example.com', priority=TaskPriority.HIGH)

	try:
		await orchestrator.add_task(task)

		# Start orchestration in background
		run_task = asyncio.create_task(orchestrator.run())

		# Wait a bit for task processing
		await asyncio.sleep(2)

		# Stop orchestration
		await orchestrator.stop()
		await run_task

		# Check results
		assert len(orchestrator.state.completed_tasks) > 0 or len(
			orchestrator.state.failed_tasks
		) > 0

	finally:
		await orchestrator.shutdown()


async def test_multi_agent_coordination(multi_agent_config):
	"""Test coordination between multiple agents."""
	orchestrator = Orchestrator(multi_agent_config)
	await orchestrator.initialize()

	try:
		agents = orchestrator.agent_registry.list_agents()
		assert len(agents) == 3

		# Check agent roles
		roles = {agent.config.role for agent in agents}
		assert AgentRole.COORDINATOR in roles
		assert AgentRole.NAVIGATOR in roles
		assert AgentRole.RESEARCHER in roles

		# Check coordinator is set
		assert orchestrator.config.coordinator_agent is not None

	finally:
		await orchestrator.shutdown()


async def test_agent_status_updates(minimal_config):
	"""Test agent status updates."""
	from bubus import EventBus

	event_bus = EventBus()
	orchestrator = Orchestrator(minimal_config, event_bus=event_bus)
	await orchestrator.initialize()

	agent = orchestrator.agent_registry.list_agents()[0]

	try:
		# Update status
		await orchestrator.agent_registry.update_agent_status(
			agent.id, AgentStatus.ACTING, task_id='test-task'
		)

		assert agent.status == AgentStatus.ACTING
		assert agent.current_task_id == 'test-task'

	finally:
		await orchestrator.shutdown()


async def test_orchestrator_stats(minimal_config):
	"""Test orchestrator statistics collection."""
	orchestrator = Orchestrator(minimal_config)
	await orchestrator.initialize()

	try:
		stats = orchestrator.get_stats()

		assert 'session_id' in stats
		assert 'status' in stats
		assert 'tasks' in stats
		assert 'agents' in stats

		assert stats['tasks']['pending'] == 0
		assert stats['tasks']['active'] == 0
		assert stats['agents']['total_agents'] == 1

	finally:
		await orchestrator.shutdown()
