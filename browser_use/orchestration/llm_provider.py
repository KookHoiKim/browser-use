"""LLM provider factory with proxy support for orchestration system."""

import logging
from typing import Any

import httpx

from browser_use.llm.base import BaseChatModel
from browser_use.orchestration.views import LLMProviderConfig, LLMProviderType

logger = logging.getLogger(__name__)


class LLMProviderFactory:
	"""Factory for creating LLM providers with proxy support."""

	@staticmethod
	def _create_http_client(config: LLMProviderConfig) -> httpx.AsyncClient | None:
		"""Create HTTP client with proxy configuration if needed.

		Args:
			config: LLM provider configuration

		Returns:
			Configured httpx.AsyncClient or None if no proxy needed
		"""
		if not config.proxy.enabled:
			return None

		proxies = {}
		if config.proxy.http_proxy:
			proxies['http://'] = config.proxy.http_proxy
		if config.proxy.https_proxy:
			proxies['https://'] = config.proxy.https_proxy

		if not proxies:
			logger.warning(f'Proxy enabled for {config.name} but no proxy URLs configured')
			return None

		# Create httpx client with proxy
		client = httpx.AsyncClient(
			proxies=proxies,  # type: ignore
			timeout=httpx.Timeout(config.timeout),
			follow_redirects=True,
		)

		logger.info(f'Created HTTP client with proxy for {config.name}: {proxies}')
		return client

	@staticmethod
	def create_openai_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create OpenAI-compatible provider.

		Args:
			config: LLM provider configuration

		Returns:
			Configured ChatOpenAI instance
		"""
		from browser_use.llm.openai.chat import ChatOpenAI

		http_client = LLMProviderFactory._create_http_client(config)

		kwargs: dict[str, Any] = {
			'model': config.model_name,
			'temperature': config.temperature,
			'max_retries': config.max_retries,
			'timeout': config.timeout,
		}

		if config.api_key:
			kwargs['api_key'] = config.api_key

		if config.api_base:
			kwargs['base_url'] = config.api_base

		if http_client:
			kwargs['http_client'] = http_client

		if config.max_tokens:
			kwargs['max_completion_tokens'] = config.max_tokens

		logger.info(f'Creating OpenAI provider: {config.name} (model: {config.model_name})')
		return ChatOpenAI(**kwargs)

	@staticmethod
	def create_azure_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create Azure OpenAI provider.

		Args:
			config: LLM provider configuration

		Returns:
			Configured Azure ChatOpenAI instance
		"""
		from browser_use.llm.openai.chat import ChatOpenAI

		if not config.api_key:
			raise ValueError(f'Azure provider {config.name} requires api_key')
		if not config.api_base:
			raise ValueError(f'Azure provider {config.name} requires api_base')
		if not config.azure_deployment:
			raise ValueError(f'Azure provider {config.name} requires azure_deployment')

		http_client = LLMProviderFactory._create_http_client(config)

		kwargs: dict[str, Any] = {
			'model': config.azure_deployment,
			'api_key': config.api_key,
			'base_url': config.api_base,
			'temperature': config.temperature,
			'max_retries': config.max_retries,
			'timeout': config.timeout,
		}

		if http_client:
			kwargs['http_client'] = http_client

		if config.max_tokens:
			kwargs['max_completion_tokens'] = config.max_tokens

		# Azure-specific headers
		if config.api_version:
			kwargs['default_query'] = {'api-version': config.api_version}

		logger.info(
			f'Creating Azure provider: {config.name} (deployment: {config.azure_deployment})'
		)
		return ChatOpenAI(**kwargs)

	@staticmethod
	def create_anthropic_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create Anthropic Claude provider.

		Args:
			config: LLM provider configuration

		Returns:
			Configured ChatAnthropic instance
		"""
		from browser_use.llm.anthropic.chat import ChatAnthropic

		http_client = LLMProviderFactory._create_http_client(config)

		kwargs: dict[str, Any] = {
			'model_name': config.model_name,
			'temperature': config.temperature,
			'max_retries': config.max_retries,
			'timeout': config.timeout,
		}

		if config.api_key:
			kwargs['api_key'] = config.api_key

		if config.api_base:
			kwargs['base_url'] = config.api_base

		if http_client:
			kwargs['http_client'] = http_client

		if config.max_tokens:
			kwargs['max_tokens'] = config.max_tokens

		logger.info(f'Creating Anthropic provider: {config.name} (model: {config.model_name})')
		return ChatAnthropic(**kwargs)

	@staticmethod
	def create_google_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create Google Gemini provider.

		Args:
			config: LLM provider configuration

		Returns:
			Configured ChatGoogle instance
		"""
		from browser_use.llm.google.chat import ChatGoogle

		kwargs: dict[str, Any] = {
			'model': config.model_name,
			'temperature': config.temperature,
		}

		if config.api_key:
			kwargs['api_key'] = config.api_key

		if config.max_tokens:
			kwargs['max_output_tokens'] = config.max_tokens

		logger.info(f'Creating Google provider: {config.name} (model: {config.model_name})')
		return ChatGoogle(**kwargs)

	@staticmethod
	def create_groq_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create Groq provider.

		Args:
			config: LLM provider configuration

		Returns:
			Configured Groq ChatOpenAI instance
		"""
		from browser_use.llm.openai.chat import ChatOpenAI

		http_client = LLMProviderFactory._create_http_client(config)

		kwargs: dict[str, Any] = {
			'model': config.model_name,
			'api_key': config.api_key or 'dummy',
			'base_url': config.api_base or 'https://api.groq.com/openai/v1',
			'temperature': config.temperature,
			'max_retries': config.max_retries,
			'timeout': config.timeout,
		}

		if http_client:
			kwargs['http_client'] = http_client

		if config.max_tokens:
			kwargs['max_completion_tokens'] = config.max_tokens

		logger.info(f'Creating Groq provider: {config.name} (model: {config.model_name})')
		return ChatOpenAI(**kwargs)

	@staticmethod
	def create_vllm_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create vLLM provider (OpenAI-compatible API).

		Args:
			config: LLM provider configuration

		Returns:
			Configured vLLM ChatOpenAI instance
		"""
		from browser_use.llm.openai.chat import ChatOpenAI

		if not config.api_base:
			raise ValueError(f'vLLM provider {config.name} requires api_base')

		http_client = LLMProviderFactory._create_http_client(config)

		kwargs: dict[str, Any] = {
			'model': config.model_name,
			'base_url': config.api_base,
			'temperature': config.temperature,
			'max_retries': config.max_retries,
			'timeout': config.timeout,
			'api_key': config.api_key or 'EMPTY',  # vLLM often doesn't require a key
		}

		if http_client:
			kwargs['http_client'] = http_client

		if config.max_tokens:
			kwargs['max_completion_tokens'] = config.max_tokens

		logger.info(f'Creating vLLM provider: {config.name} (model: {config.model_name})')
		return ChatOpenAI(**kwargs)

	@staticmethod
	def create_provider(config: LLMProviderConfig) -> BaseChatModel:
		"""Create LLM provider based on configuration.

		Args:
			config: LLM provider configuration

		Returns:
			Configured BaseChatModel instance

		Raises:
			ValueError: If provider type is not supported
		"""
		provider_map = {
			LLMProviderType.OPENAI: LLMProviderFactory.create_openai_provider,
			LLMProviderType.AZURE: LLMProviderFactory.create_azure_provider,
			LLMProviderType.ANTHROPIC: LLMProviderFactory.create_anthropic_provider,
			LLMProviderType.GOOGLE: LLMProviderFactory.create_google_provider,
			LLMProviderType.GROQ: LLMProviderFactory.create_groq_provider,
			LLMProviderType.VLLM: LLMProviderFactory.create_vllm_provider,
		}

		if config.provider_type not in provider_map:
			raise ValueError(
				f'Unsupported provider type: {config.provider_type}. '
				f'Supported types: {list(provider_map.keys())}'
			)

		factory_func = provider_map[config.provider_type]
		return factory_func(config)


class LLMProviderRegistry:
	"""Registry for managing multiple LLM providers."""

	def __init__(self):
		self._providers: dict[str, BaseChatModel] = {}
		self._configs: dict[str, LLMProviderConfig] = {}

	def register(self, config: LLMProviderConfig) -> None:
		"""Register an LLM provider.

		Args:
			config: LLM provider configuration
		"""
		if config.name in self._providers:
			logger.warning(f'Overwriting existing provider: {config.name}')

		provider = LLMProviderFactory.create_provider(config)
		self._providers[config.name] = provider
		self._configs[config.name] = config

		logger.info(f'Registered LLM provider: {config.name}')

	def get(self, name: str) -> BaseChatModel:
		"""Get LLM provider by name.

		Args:
			name: Provider name

		Returns:
			BaseChatModel instance

		Raises:
			KeyError: If provider not found
		"""
		if name not in self._providers:
			raise KeyError(f'LLM provider not found: {name}. Available: {list(self._providers.keys())}')
		return self._providers[name]

	def get_config(self, name: str) -> LLMProviderConfig:
		"""Get LLM provider configuration.

		Args:
			name: Provider name

		Returns:
			LLMProviderConfig instance

		Raises:
			KeyError: If provider not found
		"""
		if name not in self._configs:
			raise KeyError(f'LLM provider config not found: {name}')
		return self._configs[name]

	def list_providers(self) -> list[str]:
		"""List all registered provider names.

		Returns:
			List of provider names
		"""
		return list(self._providers.keys())

	def clear(self) -> None:
		"""Clear all registered providers."""
		self._providers.clear()
		self._configs.clear()
		logger.info('Cleared all LLM providers')
