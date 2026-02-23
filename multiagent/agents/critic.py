"""Critic/Verifier agent - reviews state and planner decisions."""

from __future__ import annotations

import logging

from multiagent.agents.base import BaseAgent
from multiagent.agents.views import CriticVerdictModel, PlannerDecision, parse_structured_response
from multiagent.config import AgentConfig

logger = logging.getLogger(__name__)

class CriticAgent(BaseAgent):
	"""Reviews state + planner draft; detects loops/failures; proposes fixes or abort."""

	def __init__(self, config: AgentConfig) -> None:
		super().__init__('critic', config)

	async def critique(
		self,
		task: str,
		state_description: str,
		planner_response: PlannerDecision,
		step_number: int,
		history_summary: str,
		loop_detected: bool = False,
		screenshot_b64: str | None = None,
	) -> CriticVerdictModel:
		"""Review the planner's proposed action and provide feedback.

		Returns a typed critic verdict.
		"""
		parts = [
			f'## Task\n{task}',
			f'## Step {step_number}',
			f'## Current Browser State\n{state_description}',
			f'## Recent History\n{history_summary}',
			'## Planner Proposed Action\n'
			f'{planner_response.model_dump_json(indent=2)}',
		]

		if loop_detected:
			parts.append(
				'## WARNING: Loop Detected\n'
				'The agent appears to be repeating the same actions. '
				'Consider recommending a different approach or aborting.'
			)

		parts.append(
			'## Instructions\n'
			'Review the planner\'s proposed action and respond with ONLY one JSON object (no markdown, no prose) using this exact schema:\n'
			'{\n'
			'  "verdict": "approve" | "revise" | "abort",\n'
			'  "feedback": string,\n'
			'  "revision": string | null,\n'
			'  "abort_reason": string | null\n'
			'}\n'
			'Rules:\n'
			'- If verdict="approve": revision=null, abort_reason=null.\n'
			'- If verdict="revise": revision must be non-empty, abort_reason=null.\n'
			'- If verdict="abort": abort_reason must be non-empty, revision=null.'
		)

		user_msg = '\n\n'.join(parts)

		images = None
		if screenshot_b64:
			images = [{'url': f'data:image/png;base64,{screenshot_b64}'}]

		response = await self.invoke(user_msg, images=images)
		parse_error: Exception | None = None
		try:
			return parse_structured_response(response, CriticVerdictModel)
		except Exception as exc:
			parse_error = exc
			logger.warning('Critic response parse failed on first attempt: %s', exc)

		fallback_msg = (
			f'{user_msg}\n\n'
			'## Validation Error\n'
			f'Your previous response failed schema validation: {parse_error}.\n'
			'Return ONLY a corrected JSON object matching the schema exactly.'
		)
		fallback_response = await self.invoke(fallback_msg, images=images)
		return parse_structured_response(fallback_response, CriticVerdictModel)
