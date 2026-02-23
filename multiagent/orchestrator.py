"""Multi-agent orchestrator that wraps the browser-use Agent step loop.

Design:
- Creates and owns a real browser-use Agent for browser interaction.
- Before each Agent step, consults advisory agents (Planner/Searcher/Critic).
- Injects advisory context right before the browser-agent LLM call via on_before_llm_call hook.
- Delegates actual browser action execution entirely to browser-use Agent.
- Returns the same AgentHistoryList as Agent.run().
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

from browser_use.agent.service import Agent
from browser_use.agent.views import AgentHistoryList, AgentHistory, ActionResult
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.browser.views import BrowserStateHistory

from multiagent.agents.planner import PlannerAgent
from multiagent.agents.searcher import SearcherAgent, SearcherResult
from multiagent.agents.critic import CriticAgent
from multiagent.agents.views import PlannerDecision, CriticVerdictModel
from multiagent.config import MultiAgentConfig, load_config
from multiagent.logging import RunLogger
from multiagent.detailed_logging import wrap_llm_with_logging

logger = logging.getLogger('multiagent.orchestrator')




class OrchestratorState:
	"""Runtime orchestration state used for risk-scored policy routing."""

	def __init__(self) -> None:
		self.loop_detected: bool = False
		self.recent_error_count: int = 0
		self.no_progress_steps: int = 0
		self.risk_score: int = 0

	def compute_risk_score(self) -> int:
		"""Compute an integer risk score from recent execution signals."""
		score = 0
		if self.loop_detected:
			score += 4
		score += min(self.recent_error_count, 5)
		score += min(self.no_progress_steps, 5)
		self.risk_score = score
		return score


class RiskPolicyDecision:
	"""Per-step policy decision with enabled advisors and per-step budgets."""

	def __init__(self, name: str, use_searcher: bool, use_critic: bool, max_calls: int, max_tokens: int) -> None:
		self.name = name
		self.use_searcher = use_searcher
		self.use_critic = use_critic
		self.max_calls = max_calls
		self.max_tokens = max_tokens


class MultiAgentOrchestrator:
	"""Planner-centric orchestrator: one environment step -> one action.

	For each browser-use step:
	1. Get browser state via browser-use Agent internals.
	2. Optionally invoke Searcher (first step, stuck, or loop).
	3. Ask Planner for the action (with Searcher intel if any).
	4. Ask Critic to review (always in v1).
	5. Execute the action via the real browser-use Agent step.
	6. Log everything.
	"""

	def __init__(
		self,
		task: str,
		config: MultiAgentConfig,
		config_path: str | Path | None = None,
		browser_profile: BrowserProfile | None = None,
		browser_session: BrowserSession | None = None,
	) -> None:
		self.task = task
		self.config = config
		self.run_logger = RunLogger(config, config_path)

		# Build advisory agents from config
		self.planner: PlannerAgent | None = None
		self.searcher: SearcherAgent | None = None
		self.critic: CriticAgent | None = None
		self._init_agents()

		# Browser-use agent (the real executor)
		self.browser_profile = browser_profile or BrowserProfile()
		self.browser_session = browser_session

		# State tracking
		self.recent_actions: deque[str] = deque(maxlen=self.config.orchestrator.loop_detection_window)
		self.critic_reject_count: int = 0
		self.step_number: int = 0
		self.state = OrchestratorState()

		# Detailed logging directory
		self.detailed_log_dir = self.run_logger.run_dir / 'detailed_llm_logs'
		if self.config.logging.detailed_llm_logging:
			self.detailed_log_dir.mkdir(parents=True, exist_ok=True)

	def _init_agents(self) -> None:
		"""Initialize advisory agents from config and wrap their LLMs if detailed logging is enabled."""
		for name, agent_cfg in self.config.agents.items():
			if not agent_cfg.enabled:
				continue

			agent = None
			if name == 'planner':
				agent = PlannerAgent(agent_cfg)
				self.planner = agent
			elif name == 'searcher':
				agent = SearcherAgent(agent_cfg)
				self.searcher = agent
			elif name == 'critic':
				agent = CriticAgent(agent_cfg)
				self.critic = agent
			else:
				logger.warning(f'Unknown agent type in config: {name!r}, skipping')
				continue

			# Wrap the agent's LLM with detailed logging if enabled
			if agent and self.config.logging.detailed_llm_logging:
				agent.llm = wrap_llm_with_logging(
					agent.llm,
					agent_name=name,
					log_dir=self.detailed_log_dir,
					step_number=None,  # Will be updated per step
					enabled=True,
				)

		assert self.planner is not None, 'Planner agent must be enabled'

	def _detect_loop(self) -> bool:
		"""Check if recent actions suggest the agent is stuck in a loop."""
		if len(self.recent_actions) < self.config.orchestrator.loop_detection_threshold:
			return False

		# Check if the last N actions are all identical
		threshold = self.config.orchestrator.loop_detection_threshold
		recent = list(self.recent_actions)[-threshold:]
		return len(set(recent)) == 1

	def _build_history_summary(self, agent: Agent) -> str:
		"""Build a concise summary of recent action history."""
		if not agent.history.history:
			return 'No actions taken yet.'

		lines = []
		for i, item in enumerate(agent.history.history[-5:]):  # Last 5 steps
			if item.model_output and item.model_output.action:
				for action in item.model_output.action:
					action_dict = action.model_dump(exclude_none=True, exclude_unset=True)
					lines.append(f'Step {i}: {json.dumps(action_dict, default=str)[:200]}')
			if item.result:
				for r in item.result:
					if r.error:
						lines.append(f'  -> Error: {r.error[:100]}')
					elif r.extracted_content:
						lines.append(f'  -> Content: {r.extracted_content[:100]}')
					elif r.is_done:
						lines.append(f'  -> Done (success={r.success})')

		return '\n'.join(lines) if lines else 'No action history available.'

	def _build_state_description(self, agent: Agent) -> str:
		"""Build a text description of current browser state for advisory agents."""
		session = agent.browser_session
		if session is None:
			return 'Browser session not available.'

		parts = []
		# Use cached state from the agent if available
		state = agent.state
		if state.last_model_output:
			if state.last_model_output.next_goal:
				parts.append(f'Current goal: {state.last_model_output.next_goal}')
			if state.last_model_output.memory:
				parts.append(f'Agent memory: {state.last_model_output.memory}')

		if state.last_result:
			last = state.last_result[-1]
			if last.error:
				parts.append(f'Last action error: {last.error}')
			elif last.extracted_content:
				parts.append(f'Last extracted: {last.extracted_content[:300]}')

		return '\n'.join(parts) if parts else 'Initial state - no actions taken yet.'

	def _get_action_space(self, agent: Agent) -> str:
		"""Get description of available actions."""
		if agent.tools and agent.tools.registry:
			return agent.tools.registry.get_prompt_description()
		return 'Standard browser-use actions: click, type, scroll, navigate, search, done, etc.'

	def _get_screenshot_b64(self, agent: Agent) -> str | None:
		"""Extract the last screenshot from agent history."""
		if agent.history.history:
			last_state = agent.history.history[-1].state
			if last_state and last_state.screenshot_path:
				try:
					import base64
					path = Path(last_state.screenshot_path)
					if path.exists():
						return base64.b64encode(path.read_bytes()).decode()
				except Exception:
					pass
		return None



	def _recent_error_rate(self, agent: Agent, window: int = 5) -> float:
		"""Compute error ratio for the last N environment steps."""
		items = agent.history.history[-window:]
		if not items:
			return 0.0
		error_steps = 0
		for item in items:
			if any((result.error is not None) for result in item.result):
				error_steps += 1
		return error_steps / len(items)

	def _recent_error_count(self, agent: Agent, window: int = 5) -> int:
		"""Count steps with errors in the recent window."""
		items = agent.history.history[-window:]
		if not items:
			return 0
		return sum(1 for item in items if any((result.error is not None) for result in item.result))

	def _recent_no_progress_steps(self, agent: Agent, window: int = 5) -> int:
		"""Count recent steps where no meaningful progress was observed."""
		items = agent.history.history[-window:]
		if not items:
			return 0
		no_progress = 0
		for item in items:
			if not item.result:
				no_progress += 1
				continue
			last = item.result[-1]
			if last.is_done:
				continue
			if last.error:
				no_progress += 1
				continue
			if not (last.extracted_content or '').strip():
				no_progress += 1
		return no_progress

	def _select_risk_policy(self, risk_score: int) -> RiskPolicyDecision:
		"""Select advisor policy and per-step budgets from risk score."""
		cfg = self.config.orchestrator
		if risk_score >= cfg.risk_high_threshold:
			return RiskPolicyDecision(
				name='high',
				use_searcher=True,
				use_critic=True,
				max_calls=cfg.policy_call_budget_high,
				max_tokens=cfg.policy_token_budget_high,
			)
		if risk_score >= cfg.risk_low_threshold:
			return RiskPolicyDecision(
				name='medium',
				use_searcher=False,
				use_critic=True,
				max_calls=cfg.policy_call_budget_medium,
				max_tokens=cfg.policy_token_budget_medium,
			)
		return RiskPolicyDecision(
			name='low',
			use_searcher=False,
			use_critic=False,
			max_calls=cfg.policy_call_budget_low,
			max_tokens=cfg.policy_token_budget_low,
		)

	def _has_info_gap_signal(self, state_desc: str, history_summary: str) -> bool:
		"""Detect text signals that imply missing information."""
		blob = f'{state_desc}\n{history_summary}'.lower()
		keywords = (
			'unknown',
			'not sure',
			'missing',
			'need more information',
			'cannot find',
			'unclear',
			'no result',
			'insufficient',
		)
		return any(keyword in blob for keyword in keywords)

	def _resolve_searcher_mode(
		self,
		agent_ref: Agent,
		loop_detected: bool,
		state_desc: str,
		history_summary: str,
	) -> tuple[bool, str | None, list[str]]:
		"""Decide whether to call searcher and which mode to use."""
		if self.searcher is None or not self.searcher.config.enabled:
			return False, None, []

		if self.step_number == 1 and self.config.orchestrator.searcher_on_first_step:
			mode = self.config.orchestrator.searcher_mode
			return True, ('llm_only' if mode == 'adaptive' else mode), ['first_step']

		mode = self.config.orchestrator.searcher_mode
		if mode == 'llm_only':
			return False, None, []
		if mode == 'browser':
			if loop_detected:
				return True, 'browser', ['loop_detected']
			return False, None, []

		error_rate = self._recent_error_rate(agent_ref)
		has_info_gap = self._has_info_gap_signal(state_desc, history_summary)
		triggers: list[str] = []
		if loop_detected:
			triggers.append('loop_detected')
		if error_rate >= 0.4:
			triggers.append(f'recent_error_rate={error_rate:.2f}')
		if has_info_gap:
			triggers.append('info_gap_keywords')

		if not triggers:
			return False, None, []

		chosen_mode = 'browser' if ('loop_detected' in triggers or error_rate >= 0.4) else 'llm_only'
		return True, chosen_mode, triggers


	def _log_advisory_injection_verification(self) -> None:
		"""Verify advisory markers appear in browser-agent detailed input logs."""
		if not self.config.logging.detailed_llm_logging:
			return

		browser_logs = sorted(self.detailed_log_dir.glob('step_*_browser-agent_call_*.json'))
		if not browser_logs:
			logger.warning('Advisory verification: no browser-agent detailed logs found')
			return

		found_planner = False
		found_critic = False
		for log_path in browser_logs:
			try:
				payload = json.loads(log_path.read_text(encoding='utf-8'))
			except Exception as exc:
				logger.warning(f'Advisory verification: failed to parse {log_path.name}: {exc}')
				continue

			for msg in payload.get('messages', []):
				if msg.get('role') != 'user':
					continue
				content = msg.get('content')
				if isinstance(content, str):
					if '[Planner Guidance]' in content:
						found_planner = True
					if '[Critic Feedback' in content:
						found_critic = True

		logger.info(
			'Advisory verification (browser-agent input): '
			f'[Planner Guidance]={found_planner}, [Critic Feedback]={found_critic}, files_scanned={len(browser_logs)}'
		)

	async def run(self) -> AgentHistoryList:
		"""Execute the task through multi-agent orchestration.

		Returns the same AgentHistoryList type as Agent.run().
		"""
		from multiagent.providers.base import create_llm_from_config

		# Create the underlying browser-use Agent with the planner's LLM
		planner_llm = create_llm_from_config(self.config.agents['planner'].provider)

		# Wrap the browser-use agent's LLM with detailed logging if enabled
		if self.config.logging.detailed_llm_logging:
			planner_llm = wrap_llm_with_logging(
				planner_llm,
				agent_name='browser-agent',
				log_dir=self.detailed_log_dir,
				step_number=None,  # Will be updated per step
				enabled=True,
			)

		agent = Agent(
			task=self.task,
			llm=planner_llm,
			browser_profile=self.browser_profile,
			browser_session=self.browser_session,
			max_actions_per_step=1,  # One action per step for multi-agent control
		)

		max_steps = self.config.orchestrator.max_steps

		logger.info(f'Starting multi-agent orchestration for task: {self.task[:100]}')
		logger.info(f'Max steps: {max_steps}, Run dir: {self.run_logger.run_dir}')

		# Advisory context to inject into agent steps
		self._advisory_context: str | None = None
		self._advisory_context_key: str | None = None
		self._policy_tokens_total: int = 0
		run_started = time.perf_counter()

		async def on_step_start(agent_ref: Agent) -> None:
			"""Hook called before each Agent step - consult advisory agents."""
			self.step_number = agent_ref.state.n_steps

			# Update step number in all LLM logging wrappers
			if self.config.logging.detailed_llm_logging:
				for agent in [self.planner, self.searcher, self.critic]:
					if agent and hasattr(agent.llm, 'update_step_number'):
						agent.llm.update_step_number(self.step_number)  # type: ignore
				if hasattr(agent_ref.llm, 'update_step_number'):
					agent_ref.llm.update_step_number(self.step_number)  # type: ignore

			state_desc = self._build_state_description(agent_ref)
			history_summary = self._build_history_summary(agent_ref)
			action_space = self._get_action_space(agent_ref)
			screenshot = self._get_screenshot_b64(agent_ref)
			loop_detected = self._detect_loop()

			self.state.loop_detected = loop_detected
			self.state.recent_error_count = self._recent_error_count(agent_ref)
			self.state.no_progress_steps = self._recent_no_progress_steps(agent_ref)
			risk_score = self.state.compute_risk_score()
			risk_policy = self._select_risk_policy(risk_score) if self.config.orchestrator.use_risk_policy else RiskPolicyDecision(
				name='legacy',
				use_searcher=True,
				use_critic=self.config.orchestrator.always_use_critic,
				max_calls=999,
				max_tokens=999999,
			)
			policy_calls_used = 0
			policy_tokens_used = 0

			# Log step inputs
			step_inputs: dict[str, Any] = {
				'step': self.step_number,
				'state': state_desc[:500],
				'loop_detected': loop_detected,
				'risk_score': risk_score,
				'risk_policy': risk_policy.name,
				'recent_error_count': self.state.recent_error_count,
				'no_progress_steps': self.state.no_progress_steps,
			}

			searcher_summary: str | None = None
			searcher_result: SearcherResult | None = None
			critic_feedback: str | None = None
			searcher_used = False
			searcher_mode_used: str | None = None
			searcher_latency_ms: int | None = None
			searcher_triggers: list[str] = []

			# --- Searcher ---
			should_search, selected_mode, searcher_triggers = self._resolve_searcher_mode(
				agent_ref=agent_ref,
				loop_detected=loop_detected,
				state_desc=state_desc,
				history_summary=history_summary,
			)

			if should_search and risk_policy.use_searcher and policy_calls_used < risk_policy.max_calls and policy_tokens_used < risk_policy.max_tokens:
				assert self.searcher is not None
				assert selected_mode is not None
				searcher_used = True
				searcher_mode_used = selected_mode
				started = time.perf_counter()
				try:
					if selected_mode == 'browser':
						searcher_result = await self.searcher.search(
							query=self.task,
							task_context=f'Step {self.step_number}\n{state_desc}\n\n{history_summary}',
							browser_profile=BrowserProfile(headless=True),
						)
					else:
						searcher_result = await self.searcher.gather_info(
							task=self.task,
							state_description=state_desc,
							step_number=self.step_number,
							history_summary=history_summary,
						)
					searcher_latency_ms = int((time.perf_counter() - started) * 1000)
					searcher_summary = searcher_result.to_planner_section()
					policy_calls_used += 1
					policy_tokens_used += max(1, len(searcher_summary) // 4)
					logger.info(
						f'Step {self.step_number}: Searcher mode={selected_mode} returned ' 
						f'{len(searcher_summary)} chars in {searcher_latency_ms}ms (triggers={searcher_triggers})'
					)
				except Exception as e:
					searcher_latency_ms = int((time.perf_counter() - started) * 1000)
					logger.error(f'Step {self.step_number}: Searcher failed: {e}')
					searcher_summary = f'Searcher error: {e}'
			elif should_search and not risk_policy.use_searcher:
				logger.info(f'Step {self.step_number}: Risk policy={risk_policy.name} skipped searcher')
			elif should_search:
				logger.info(f'Step {self.step_number}: Searcher skipped due to policy budget limits')

			# --- Planner (pre-step advisory) ---
			planner_response: PlannerDecision | None = None
			if self.planner is not None and policy_calls_used < risk_policy.max_calls and policy_tokens_used < risk_policy.max_tokens:
				try:
					planner_response = await self.planner.plan(
						task=self.task,
						state_description=state_desc,
						action_space=action_space,
						step_number=self.step_number,
						history_summary=history_summary,
						searcher_summary=searcher_summary,
						screenshot_b64=screenshot,
					)
					planner_preview = planner_response.model_dump_json()
					policy_calls_used += 1
					policy_tokens_used += max(1, len(planner_preview) // 4)
					logger.info(f'Step {self.step_number}: Planner responded ({len(planner_preview)} chars)')
				except Exception as e:
					logger.error(f'Step {self.step_number}: Planner failed: {e}')
			elif self.planner is not None:
				logger.warning(f'Step {self.step_number}: Planner skipped due to risk-policy budget limits')

			# --- Critic ---
			critic_verdict: CriticVerdictModel | None = None
			if (
				self.critic is not None
				and self.critic.config.enabled
				and self.config.orchestrator.always_use_critic
				and risk_policy.use_critic
				and policy_calls_used < risk_policy.max_calls
				and policy_tokens_used < risk_policy.max_tokens
				and planner_response
			):
				try:
					critic_verdict = await self.critic.critique(
						task=self.task,
						state_description=state_desc,
						planner_response=planner_response,
						step_number=self.step_number,
						history_summary=history_summary,
						loop_detected=loop_detected,
						screenshot_b64=screenshot,
					)
					critic_feedback = critic_verdict.feedback
					policy_calls_used += 1
					policy_tokens_used += max(1, len((critic_feedback or '')) // 4)

					if critic_verdict.should_abort:
						self.critic_reject_count += 1
						logger.warning(
							f'Step {self.step_number}: Critic recommends ABORT '
							f'({self.critic_reject_count}/{self.config.orchestrator.abort_on_critic_reject_count}): '
							f'{critic_verdict.abort_reason}'
						)
						if self.critic_reject_count >= self.config.orchestrator.abort_on_critic_reject_count:
							logger.error('Critic abort threshold reached, stopping agent')
							agent_ref.state.stopped = True
					elif critic_verdict.should_revise:
						logger.info(f'Step {self.step_number}: Critic suggests revision: {critic_verdict.revision}')
					else:
						logger.info(f'Step {self.step_number}: Critic approved')

				except Exception as e:
					logger.error(f'Step {self.step_number}: Critic failed: {e}')

			# Build advisory context to inject
			advisory_parts = []
			if searcher_summary:
				advisory_parts.append(f'[Searcher Intel]\n{searcher_summary}')
			if planner_response:
				advisory_parts.append('[Planner Guidance]\n' + planner_response.model_dump_json(indent=2))
			if critic_feedback and critic_verdict is not None:
				advisory_parts.append(f'[Critic Feedback ({critic_verdict.verdict})]\n{critic_feedback}')

			self._advisory_context = '\n\n'.join(advisory_parts) if advisory_parts else None

			self._advisory_context_key = f'advisory_step_{self.step_number}' if self._advisory_context else None

			self._policy_tokens_total += policy_tokens_used

			# Log step data
			self.run_logger.log_step(
				step_number=self.step_number,
				agent_inputs={
					**step_inputs,
					'advisory_context_key': self._advisory_context_key,
					'advisory_injected': None,
				},
				agent_outputs={
					'policy_name': risk_policy.name,
					'policy_calls_used': policy_calls_used,
					'policy_calls_budget': risk_policy.max_calls,
					'policy_tokens_used_est': policy_tokens_used,
					'policy_tokens_budget': risk_policy.max_tokens,
					'searcher': searcher_summary[:500] if searcher_summary else None,
					'searcher_sources': searcher_result.sources if searcher_result else None,
					'searcher_triggers': searcher_triggers or None,
					'planner_typed': planner_response.model_dump(mode='json') if planner_response else None,
					'critic_typed': critic_verdict.model_dump(mode='json') if critic_verdict else None,
					'advisory_context_preview': self._advisory_context[:500] if self._advisory_context else None,
				},
				loop_detected=loop_detected,
				critic_verdict=critic_verdict.verdict if critic_verdict else None,
				searcher_used=searcher_used,
				searcher_mode_used=searcher_mode_used,
				searcher_latency_ms=searcher_latency_ms,
			)

		async def on_before_llm_call(agent_ref: Agent) -> None:
			"""Inject prepared advisory context after step-state prep and before LLM call."""
			if not self._advisory_context:
				return

			advisory_dedupe_key = self._advisory_context_key or f'advisory_step_{self.step_number}'
			advisory_injected = agent_ref.add_step_context_message(
				self._advisory_context,
				dedupe_key=advisory_dedupe_key,
			)
			logger.info(
				f'Step {self.step_number}: advisory context {"injected" if advisory_injected else "deduplicated"} '
				f'(key={advisory_dedupe_key}, chars={len(self._advisory_context)})'
			)

			self.run_logger.log_step(
				step_number=self.step_number,
				agent_inputs={
					'advisory_context_key': advisory_dedupe_key,
					'advisory_injected': advisory_injected,
				},
			)

		async def on_step_end(agent_ref: Agent) -> None:
			"""Hook called after each Agent step - record action for loop detection."""
			if agent_ref.history.history:
				last_item = agent_ref.history.history[-1]
				if last_item.model_output and last_item.model_output.action:
					action_repr = json.dumps(
						last_item.model_output.action[0].model_dump(exclude_none=True, exclude_unset=True),
						default=str,
					)[:200]
					self.recent_actions.append(action_repr)

				# Update step log with action outcome
				outcome: dict[str, Any] = {}
				if last_item.result:
					last_result = last_item.result[-1]
					outcome = {
						'is_done': last_result.is_done,
						'success': last_result.success,
						'error': last_result.error,
						'extracted_content': last_result.extracted_content[:200] if last_result.extracted_content else None,
					}

				chosen_action: dict[str, Any] = {}
				if last_item.model_output and last_item.model_output.action:
					chosen_action = last_item.model_output.action[0].model_dump(
						exclude_none=True, exclude_unset=True
					)

				self.run_logger.log_step(
					step_number=self.step_number,
					action_outcome=outcome,
					chosen_action=chosen_action,
				)

				# Save screenshot artifact if configured
				if self.config.logging.save_screenshots and last_item.state and last_item.state.screenshot_path:
					try:
						src = Path(last_item.state.screenshot_path)
						if src.exists():
							self.run_logger.save_artifact(
								f'screenshot_{src.name}',
								src.read_bytes(),
								step=self.step_number,
							)
					except Exception:
						pass

		try:
			result: AgentHistoryList = await agent.run(
				max_steps=max_steps,
				on_step_start=on_step_start,
				on_before_llm_call=on_before_llm_call,
				on_step_end=on_step_end,
			)

			self._log_advisory_injection_verification()

			# Save run summary
			wall_time_seconds = time.perf_counter() - run_started
			self.run_logger.log_summary({
				'task': self.task,
				'total_steps': len(result.history),
				'is_done': result.is_done(),
				'is_successful': result.is_successful(),
				'final_result': result.final_result(),
				'errors': result.errors(),
				'planner_calls': self.planner.call_count if self.planner else 0,
				'searcher_calls': self.searcher.call_count if self.searcher else 0,
				'critic_calls': self.critic.call_count if self.critic else 0,
				'critic_reject_count': self.critic_reject_count,
				'risk_policy_enabled': self.config.orchestrator.use_risk_policy,
				'estimated_policy_tokens_total': self._policy_tokens_total,
				'wall_time_seconds': wall_time_seconds,
			})

			logger.info(
				f'Multi-agent run complete: {len(result.history)} steps, '
				f'done={result.is_done()}, success={result.is_successful()}'
			)
			logger.info(f'Logs saved to: {self.run_logger.run_dir}')

			return result

		except Exception as e:
			logger.error(f'Multi-agent orchestration failed: {e}', exc_info=True)
			self.run_logger.log_summary({
				'task': self.task,
				'error': str(e),
				'total_steps': self.step_number,
			})
			raise


async def run_multiagent(
	task: str,
	config_path: str | Path,
	browser_profile: BrowserProfile | None = None,
	browser_session: BrowserSession | None = None,
) -> AgentHistoryList:
	"""Convenience function to run a multi-agent task.

	Returns the same AgentHistoryList as single-agent Agent.run().
	"""
	config = load_config(config_path)
	orchestrator = MultiAgentOrchestrator(
		task=task,
		config=config,
		config_path=config_path,
		browser_profile=browser_profile,
		browser_session=browser_session,
	)
	return await orchestrator.run()
