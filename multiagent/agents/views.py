"""Typed response models for multi-agent advisory agents."""

from __future__ import annotations

import json
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class PlannerDecision(BaseModel):
	"""Structured planner output for a single orchestration step."""

	model_config = ConfigDict(extra='forbid')

	thinking: str = Field(description='Reasoning for the selected next action.')
	action: str = Field(description='One action name from the available action space.')
	params: dict[str, Any] = Field(default_factory=dict, description='Parameters for the selected action.')
	is_done: bool = Field(description='Whether the overall task is complete at this step.')
	success: bool | None = Field(
		default=None,
		description='Final task success flag, only valid when is_done=true.',
	)
	extracted_content: str | None = Field(
		default=None,
		description='Optional final extracted content, only valid when is_done=true.',
	)

	@model_validator(mode='after')
	def validate_completion_fields(self) -> 'PlannerDecision':
		"""Require completion-related fields only when task is marked done."""
		if self.is_done and self.success is None:
			raise ValueError('success must be provided when is_done is true')
		if not self.is_done and self.success is not None:
			raise ValueError('success must be null when is_done is false')
		if not self.is_done and self.extracted_content is not None:
			raise ValueError('extracted_content must be null when is_done is false')
		return self


class CriticVerdictModel(BaseModel):
	"""Structured critic review for planner output."""

	model_config = ConfigDict(extra='forbid')

	verdict: Literal['approve', 'revise', 'abort']
	feedback: str
	revision: str | None = None
	abort_reason: str | None = None

	@model_validator(mode='after')
	def validate_conditional_fields(self) -> 'CriticVerdictModel':
		"""Validate fields required by each verdict."""
		if self.verdict == 'revise' and not self.revision:
			raise ValueError('revision is required when verdict is revise')
		if self.verdict == 'abort' and not self.abort_reason:
			raise ValueError('abort_reason is required when verdict is abort')
		if self.verdict != 'revise' and self.revision is not None:
			raise ValueError('revision must be null unless verdict is revise')
		if self.verdict != 'abort' and self.abort_reason is not None:
			raise ValueError('abort_reason must be null unless verdict is abort')
		return self

	@property
	def should_abort(self) -> bool:
		return self.verdict == 'abort'

	@property
	def should_revise(self) -> bool:
		return self.verdict == 'revise'

	@property
	def approved(self) -> bool:
		return self.verdict == 'approve'


TModel = TypeVar('TModel', bound=BaseModel)


def parse_structured_response(response: str, model_cls: type[TModel]) -> TModel:
	"""Parse LLM output as JSON into a strict Pydantic model.

	Supports either a pure JSON body or a response containing a single JSON object.
	"""
	try:
		return model_cls.model_validate_json(response)
	except ValidationError:
		pass
	except json.JSONDecodeError:
		pass

	start = response.find('{')
	end = response.rfind('}') + 1
	if start < 0 or end <= start:
		raise ValueError('No JSON object found in model response')

	try:
		parsed = json.loads(response[start:end])
	except json.JSONDecodeError as exc:
		raise ValueError(f'Invalid JSON object in model response: {exc}') from exc

	return model_cls.model_validate(parsed)
