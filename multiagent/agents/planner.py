"""Planner agent - main reasoner and final action decider."""

from __future__ import annotations

import logging

from multiagent.agents.base import BaseAgent
from multiagent.agents.views import PlannerDecision, parse_structured_response
from multiagent.config import AgentConfig

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
	"""Produces the final single browser-use action each step.

	Takes browser state + optional advice from Searcher/Critic and decides
	the next action in browser-use's action format.
	"""

	def __init__(self, config: AgentConfig) -> None:
		super().__init__('planner', config)

	async def plan(
		self,
		task: str,
		state_description: str,
		action_space: str,
		step_number: int,
		history_summary: str,
		searcher_summary: str | None = None,
		critic_feedback: str | None = None,
		screenshot_b64: str | None = None,
	) -> PlannerDecision:
		"""Generate the next-action decision with strict schema parsing."""
		parts = [
			f'## Task\n{task}',
			f'## Step {step_number}',
			f'## Current Browser State\n{state_description}',
			f'## Action History\n{history_summary}',
			f'## Available Actions\n{action_space}',
		]

		if searcher_summary:
			parts.append(f'## Searcher Intelligence\n{searcher_summary}')

		if critic_feedback:
			parts.append(f'## Critic Feedback\n{critic_feedback}')

		parts.append(
			'## Instructions\n'
			'Analyze the current state and decide on exactly ONE action to take.\n'
			'Respond with ONLY one JSON object (no markdown, no prose) matching this exact schema:\n'
			'{\n'
			'  "thinking": string,\n'
			'  "action": string,\n'
			'  "params": object,\n'
			'  "is_done": boolean,\n'
			'  "success": boolean | null,\n'
			'  "extracted_content": string | null\n'
			'}\n'
			'Rules:\n'
			'- Use field names exactly as written.\n'
			'- If is_done=false, set success=null and extracted_content=null.\n'
			'- If is_done=true, success must be true/false and extracted_content may contain final output.'
		)

		user_msg = '\n\n'.join(parts)

		images = None
		if screenshot_b64:
			images = [{'url': f'data:image/png;base64,{screenshot_b64}'}]

		response = await self.invoke(user_msg, images=images)
		parse_error: Exception | None = None
		try:
			return parse_structured_response(response, PlannerDecision)
		except Exception as exc:
			parse_error = exc
			logger.warning('Planner response parse failed on first attempt: %s', exc)

		reask_msg = (
			f'{user_msg}\n\n'
			'## Validation Error\n'
			f'Your previous response failed schema validation: {parse_error}.\n'
			'Return ONLY a corrected JSON object matching the schema exactly.'
		)
		reask_response = await self.invoke(reask_msg, images=images)
		return parse_structured_response(reask_response, PlannerDecision)
