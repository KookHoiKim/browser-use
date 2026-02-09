"""YAML configuration loading and management for orchestration system."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from browser_use.orchestration.views import (
	AgentCapability,
	AgentConfig,
	AgentRole,
	LLMProviderConfig,
	LLMProviderType,
	OrchestrationConfig,
	ProxyConfig,
	TaskPriority,
)

logger = logging.getLogger(__name__)


class ConfigLoader:
	"""Loads and validates orchestration configuration from YAML files."""

	@staticmethod
	def _resolve_env_vars(data: Any) -> Any:
		"""Recursively resolve environment variables in configuration data.

		Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax.
		"""
		if isinstance(data, str):
			# Handle ${VAR_NAME} or ${VAR_NAME:default}
			import re

			def replace_env(match: re.Match[str]) -> str:
				var_expr = match.group(1)
				if ':' in var_expr:
					var_name, default = var_expr.split(':', 1)
					return os.environ.get(var_name.strip(), default.strip())
				else:
					var_name = var_expr.strip()
					value = os.environ.get(var_name)
					if value is None:
						raise ValueError(f'Environment variable {var_name} not found and no default provided')
					return value

			return re.sub(r'\$\{([^}]+)\}', replace_env, data)

		elif isinstance(data, dict):
			return {key: ConfigLoader._resolve_env_vars(value) for key, value in data.items()}
		elif isinstance(data, list):
			return [ConfigLoader._resolve_env_vars(item) for item in data]
		else:
			return data

	@staticmethod
	def load_yaml(file_path: str | Path) -> dict[str, Any]:
		"""Load and parse YAML configuration file."""
		path = Path(file_path)
		if not path.exists():
			raise FileNotFoundError(f'Configuration file not found: {path}')

		logger.info(f'Loading configuration from {path}')

		with open(path, 'r', encoding='utf-8') as f:
			try:
				data = yaml.safe_load(f)
				if not isinstance(data, dict):
					raise ValueError('Configuration file must contain a YAML dictionary')
				return data
			except yaml.YAMLError as e:
				raise ValueError(f'Invalid YAML syntax: {e}')

	@staticmethod
	def _parse_llm_providers(providers_data: list[dict[str, Any]]) -> list[LLMProviderConfig]:
		"""Parse LLM provider configurations."""
		providers = []

		for idx, provider_dict in enumerate(providers_data):
			try:
				# Handle proxy configuration
				proxy_data = provider_dict.get('proxy', {})
				if isinstance(proxy_data, dict):
					provider_dict['proxy'] = ProxyConfig(**proxy_data)

				# Parse provider type
				provider_type_str = provider_dict.get('provider_type', '').lower()
				try:
					provider_dict['provider_type'] = LLMProviderType(provider_type_str)
				except ValueError:
					logger.warning(
						f'Unknown provider type "{provider_type_str}", defaulting to CUSTOM'
					)
					provider_dict['provider_type'] = LLMProviderType.CUSTOM

				provider = LLMProviderConfig(**provider_dict)
				providers.append(provider)
				logger.debug(f'Loaded LLM provider: {provider.name}')

			except ValidationError as e:
				raise ValueError(f'Invalid LLM provider configuration at index {idx}: {e}')

		return providers

	@staticmethod
	def _parse_agents(agents_data: list[dict[str, Any]]) -> list[AgentConfig]:
		"""Parse agent configurations."""
		agents = []

		for idx, agent_dict in enumerate(agents_data):
			try:
				# Parse role
				role_str = agent_dict.get('role', '').lower()
				try:
					agent_dict['role'] = AgentRole(role_str)
				except ValueError:
					logger.warning(f'Unknown role "{role_str}", defaulting to CUSTOM')
					agent_dict['role'] = AgentRole.CUSTOM

				# Parse capabilities
				capabilities_data = agent_dict.get('capabilities', [])
				if isinstance(capabilities_data, list):
					agent_dict['capabilities'] = [
						AgentCapability(**cap) if isinstance(cap, dict) else cap
						for cap in capabilities_data
					]

				# Parse delegation roles
				delegation_roles_data = agent_dict.get('delegation_roles', [])
				if isinstance(delegation_roles_data, list):
					parsed_roles = []
					for role_str in delegation_roles_data:
						try:
							parsed_roles.append(AgentRole(role_str.lower()))
						except ValueError:
							logger.warning(f'Unknown delegation role "{role_str}", skipping')
					agent_dict['delegation_roles'] = parsed_roles

				agent = AgentConfig(**agent_dict)
				agents.append(agent)
				logger.debug(f'Loaded agent: {agent.name} (role: {agent.role})')

			except ValidationError as e:
				raise ValueError(f'Invalid agent configuration at index {idx}: {e}')

		return agents

	@staticmethod
	def load_config(file_path: str | Path) -> OrchestrationConfig:
		"""Load and validate complete orchestration configuration from YAML.

		Args:
			file_path: Path to YAML configuration file

		Returns:
			Validated OrchestrationConfig instance

		Raises:
			FileNotFoundError: If config file doesn't exist
			ValueError: If configuration is invalid
		"""
		# Load raw YAML
		raw_data = ConfigLoader.load_yaml(file_path)

		# Resolve environment variables
		resolved_data = ConfigLoader._resolve_env_vars(raw_data)

		try:
			# Parse LLM providers
			providers_data = resolved_data.get('llm_providers', [])
			if not providers_data:
				raise ValueError('At least one LLM provider must be configured')
			resolved_data['llm_providers'] = ConfigLoader._parse_llm_providers(providers_data)

			# Parse agents
			agents_data = resolved_data.get('agents', [])
			if not agents_data:
				raise ValueError('At least one agent must be configured')
			resolved_data['agents'] = ConfigLoader._parse_agents(agents_data)

			# Create final configuration
			config = OrchestrationConfig(**resolved_data)

			# Validate LLM provider references
			provider_names = {p.name for p in config.llm_providers}
			for agent in config.agents:
				if agent.llm_provider not in provider_names:
					raise ValueError(
						f'Agent "{agent.name}" references unknown LLM provider "{agent.llm_provider}"'
					)

			# Validate coordinator agent
			if config.coordinator_agent:
				agent_ids = {a.id for a in config.agents}
				if config.coordinator_agent not in agent_ids:
					raise ValueError(
						f'Coordinator agent ID "{config.coordinator_agent}" not found in agents'
					)

			logger.info(
				f'Successfully loaded configuration with {len(config.agents)} agents '
				f'and {len(config.llm_providers)} LLM providers'
			)

			return config

		except ValidationError as e:
			raise ValueError(f'Configuration validation failed: {e}')

	@staticmethod
	def save_config(config: OrchestrationConfig, file_path: str | Path) -> None:
		"""Save orchestration configuration to YAML file.

		Args:
			config: OrchestrationConfig to save
			file_path: Output file path
		"""
		path = Path(file_path)

		# Convert to dict and serialize
		config_dict = config.model_dump(mode='python', exclude_none=True)

		with open(path, 'w', encoding='utf-8') as f:
			yaml.safe_dump(
				config_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True
			)

		logger.info(f'Configuration saved to {path}')
