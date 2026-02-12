"""Detailed LLM input/output logging for multi-agent debugging.

This module provides a wrapper around BaseChatModel that captures and logs
all LLM interactions (full prompts + responses) to JSON files for debugging.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class LLMLoggingWrapper:
	"""Wraps a BaseChatModel to log all inputs and outputs to JSON files.

	This wrapper intercepts ainvoke() calls and saves:
	- Full system + user messages (prompts)
	- Complete LLM responses
	- Metadata (timestamp, agent name, token usage, etc.)

	Each call is saved as a separate JSON file for easy inspection.
	"""

	def __init__(
		self,
		llm: BaseChatModel,
		agent_name: str,
		log_dir: Path,
		step_number: int | None = None,
	) -> None:
		"""Initialize the logging wrapper.

		Args:
			llm: The underlying LLM to wrap
			agent_name: Name of the agent (e.g., 'planner', 'searcher', 'browser-agent')
			log_dir: Directory to save detailed logs
			step_number: Current orchestrator step number (if applicable)
		"""
		self._llm = llm
		self._agent_name = agent_name
		self._log_dir = log_dir
		self._step_number = step_number
		self._call_count = 0

		# Ensure log directory exists
		self._log_dir.mkdir(parents=True, exist_ok=True)

	def update_step_number(self, step_number: int) -> None:
		"""Update the current step number for logging context."""
		self._step_number = step_number
		self._call_count = 0  # Reset call count for new step

	@property
	def provider(self) -> str:
		return self._llm.provider

	@property
	def name(self) -> str:
		return self._llm.name

	@property
	def model(self) -> str:
		return self._llm.model

	@property
	def model_name(self) -> str:
		return self._llm.model_name

	def _serialize_message(self, msg: BaseMessage) -> dict[str, Any]:
		"""Convert a BaseMessage to a JSON-serializable dict."""
		result: dict[str, Any] = {'role': msg.role}

		# Handle content (can be str or list of content parts)
		if isinstance(msg.content, str):
			result['content'] = msg.content
		elif isinstance(msg.content, list):
			# Content parts (text + images)
			parts = []
			for part in msg.content:
				if hasattr(part, 'model_dump'):
					# Pydantic model
					part_dict = part.model_dump()
					# Truncate base64 images for readability
					if 'image_url' in part_dict and isinstance(part_dict['image_url'], dict):
						url = part_dict['image_url'].get('url', '')
						if url.startswith('data:image/') and len(url) > 100:
							part_dict['image_url']['url'] = f'{url[:100]}... [TRUNCATED {len(url)} chars]'
					parts.append(part_dict)
				else:
					parts.append(str(part))
			result['content'] = parts
		else:
			result['content'] = str(msg.content)

		return result

	def _serialize_completion(self, completion: ChatInvokeCompletion[Any]) -> dict[str, Any]:
		"""Convert a ChatInvokeCompletion to a JSON-serializable dict."""
		result: dict[str, Any] = {}

		# Handle different completion types
		if isinstance(completion.completion, BaseModel):
			result['completion'] = completion.completion.model_dump()
		elif isinstance(completion.completion, str):
			result['completion'] = completion.completion
		else:
			result['completion'] = str(completion.completion)

		# Add usage metadata
		if completion.usage:
			result['prompt_tokens'] = completion.usage.prompt_tokens
			result['completion_tokens'] = completion.usage.completion_tokens
			result['total_tokens'] = completion.usage.total_tokens
			if completion.usage.prompt_cached_tokens:
				result['prompt_cached_tokens'] = completion.usage.prompt_cached_tokens

		# Add other metadata
		if completion.stop_reason:
			result['stop_reason'] = completion.stop_reason
		if completion.thinking:
			result['thinking'] = completion.thinking

		return result

	async def ainvoke(
		self,
		messages: list[BaseMessage],
		output_format: type[T] | None = None,
		**kwargs: Any,
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		"""Invoke the LLM with logging.

		This method:
		1. Serializes input messages to JSON
		2. Calls the underlying LLM's ainvoke()
		3. Serializes the output to JSON
		4. Saves everything to a timestamped JSON file
		5. Returns the original result
		"""
		self._call_count += 1
		timestamp = datetime.now(timezone.utc)

		# Serialize input messages
		input_data = {
			'timestamp': timestamp.isoformat(),
			'agent_name': self._agent_name,
			'step_number': self._step_number,
			'call_number': self._call_count,
			'model': self._llm.model,
			'provider': self._llm.provider,
			'messages': [self._serialize_message(msg) for msg in messages],
			'output_format': output_format.__name__ if output_format else None,
			'kwargs': {k: str(v) for k, v in kwargs.items()},
		}

		# Call the underlying LLM
		try:
			result = await self._llm.ainvoke(messages, output_format, **kwargs)

			# Serialize output
			output_data = self._serialize_completion(result)
			input_data['response'] = output_data
			input_data['success'] = True

		except Exception as e:
			# Log error
			input_data['response'] = None
			input_data['success'] = False
			input_data['error'] = str(e)
			input_data['error_type'] = type(e).__name__
			raise

		finally:
			# Save to file regardless of success/failure
			self._save_log(input_data, timestamp)

		return result

	def _save_log(self, data: dict[str, Any], timestamp: datetime) -> None:
		"""Save the log data to a JSON file."""
		try:
			# Generate filename: step_NNNN_agent-name_call_N_YYYYMMDD_HHMMSS.json
			timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # milliseconds

			if self._step_number is not None:
				filename = f'step_{self._step_number:04d}_{self._agent_name}_call_{self._call_count}_{timestamp_str}.json'
			else:
				filename = f'{self._agent_name}_call_{self._call_count}_{timestamp_str}.json'

			filepath = self._log_dir / filename
			filepath.write_text(
				json.dumps(data, indent=2, ensure_ascii=False, default=str),
				encoding='utf-8',
			)

			logger.debug(f'Saved detailed log: {filepath}')

		except Exception as e:
			logger.error(f'Failed to save detailed log: {e}')


def wrap_llm_with_logging(
	llm: BaseChatModel,
	agent_name: str,
	log_dir: Path,
	step_number: int | None = None,
	enabled: bool = True,
) -> BaseChatModel:
	"""Wrap an LLM with logging if enabled.

	Args:
		llm: The LLM to wrap
		agent_name: Name of the agent using this LLM
		log_dir: Directory for detailed logs
		step_number: Current step number (if applicable)
		enabled: Whether to enable logging (if False, returns original LLM)

	Returns:
		The wrapped LLM (or original if disabled)
	"""
	if not enabled:
		return llm

	return LLMLoggingWrapper(llm, agent_name, log_dir, step_number)  # type: ignore
