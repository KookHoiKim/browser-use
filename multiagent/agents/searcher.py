"""Searcher agent - gathers information via LLM or browsing in an isolated context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from browser_use.agent.service import Agent
from browser_use.agent.views import AgentHistoryList
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from multiagent.agents.base import BaseAgent
from multiagent.config import AgentConfig
from multiagent.providers.proxy_scope import proxy_scope

logger = logging.getLogger(__name__)


@dataclass
class SearcherResult:
	"""Structured search intelligence passed to the planner."""

	mode_used: str
	query: str
	summary: str
	sources: list[str]
	evidence: list[str]
	raw_output: str

	def to_planner_section(self) -> str:
		"""Render result in sectioned format for planner consumption."""
		source_lines = [f'- {url}' for url in self.sources] or ['- (none)']
		evidence_lines = [f'- {item}' for item in self.evidence] or ['- (none)']
		return (
			f'### Searcher Mode\n{self.mode_used}\n\n'
			f'### Query\n{self.query}\n\n'
			f'### Summary\n{self.summary}\n\n'
			+ '### Sources\n' + '\n'.join(source_lines) + '\n\n'
			+ '### Evidence\n' + '\n'.join(evidence_lines)
		)


class SearcherAgent(BaseAgent):
	"""Gathers information by running a short sub-agent in an isolated browser context.

	The Searcher can open pages, click, scroll, and read content but operates
	in a separate BrowserSession to avoid contaminating the main browsing state.
	It returns only text summaries to the Planner.
	"""

	def __init__(self, config: AgentConfig) -> None:
		super().__init__('searcher', config)

	async def search(
		self,
		query: str,
		task_context: str,
		max_steps: int = 8,
		browser_profile: BrowserProfile | None = None,
	) -> SearcherResult:
		"""Run a short browsing sub-task to gather information.

		Creates an isolated BrowserSession, runs a mini browser-use Agent,
		collects results, then tears down the session.

		Returns a structured text summary.
		"""
		search_task = (
			f'You are a research assistant. Your goal is to find information relevant to this query:\n\n'
			f'Query: {query}\n\n'
			f'Context: {task_context}\n\n'
			f'Instructions:\n'
			f'- Search the web for relevant information\n'
			f'- Extract key facts, URLs, and data points\n'
			f'- When you have enough information, use the done action with a structured summary\n'
			f'- Be concise and factual\n'
			f'- Include source URLs where possible'
		)

		profile = browser_profile or BrowserProfile(headless=True)
		session = BrowserSession(browser_profile=profile)

		proxy_url = self.config.provider.proxy_url if self.config.provider.type == 'azure' else None

		try:
			with proxy_scope(proxy_url):
				search_agent = Agent(
					task=search_task,
					llm=self.llm,
					browser_session=session,
					max_actions_per_step=1,
				)
				result: AgentHistoryList = await search_agent.run(max_steps=max_steps)

			# Extract the final result
			final = result.final_result()
			if final:
				return self._build_structured_result(mode_used='browser', query=query, output=final)

			# Fallback: collect any extracted content from history
			contents = []
			for item in result.history:
				for action_result in item.result:
					if action_result.extracted_content:
						contents.append(action_result.extracted_content)

			if contents:
				combined = '\n\n'.join(contents)
				return self._build_structured_result(mode_used='browser', query=query, output=combined)

			return self._build_structured_result(mode_used='browser', query=query, output='Searcher could not find relevant information.')

		except Exception as e:
			logger.error(f'Searcher failed: {e}')
			return self._build_structured_result(mode_used='browser', query=query, output=f'Searcher encountered an error: {e}')

		finally:
			try:
				await session.stop()
			except Exception:
				pass

	@staticmethod
	def _extract_urls(text: str) -> list[str]:
		"""Extract unique URLs from freeform text."""
		import re

		matches = re.findall(r"https?://[^\s)\]}>\"']+", text)
		urls: list[str] = []
		for url in matches:
			cleaned = url.rstrip('.,;')
			if cleaned not in urls:
				urls.append(cleaned)
		return urls

	def _build_structured_result(self, mode_used: str, query: str, output: str) -> SearcherResult:
		"""Convert freeform model output into a structured SearcherResult."""
		urls = self._extract_urls(output)
		evidence = [line.strip('-*• ').strip() for line in output.splitlines() if line.strip().startswith(('-', '*', '•'))]
		if not evidence:
			evidence = [seg.strip() for seg in output.split('\n') if seg.strip()][:5]
		summary = output.strip().split('\n\n')[0][:800] or 'No summary provided.'
		return SearcherResult(
			mode_used=mode_used,
			query=query,
			summary=summary,
			sources=urls[:10],
			evidence=evidence[:8],
			raw_output=output,
		)


	async def gather_info(
		self,
		task: str,
		state_description: str,
		step_number: int,
		history_summary: str,
	) -> SearcherResult:
		"""Quick LLM-only information gathering without browsing.

		Used for lightweight queries where browsing isn't needed.
		"""
		user_msg = (
			f'## Task\n{task}\n\n'
			f'## Current State (Step {step_number})\n{state_description}\n\n'
			f'## History\n{history_summary}\n\n'
			f'## Instructions\n'
			f'Analyze the current situation and provide a concise summary of:\n'
			f'- Key facts relevant to completing the task\n'
			f'- Any missing information that should be searched for\n'
			f'- Suggested URLs or search queries if applicable\n'
			f'Respond in a structured format.'
		)
		response = await self.invoke(user_msg)
		return self._build_structured_result(mode_used='llm_only', query=task, output=response)
