#!/usr/bin/env python3
"""Benchmark runner for the Online-Mind2Web dataset using multi-agent orchestration.

Loads the full dataset from HuggingFace and runs the multi-agent orchestrator
on each task in parallel with configurable concurrency.

Usage:
    python running_dirs/run_mind2web.py --config configs/multiagent_default.yaml
    python running_dirs/run_mind2web.py --config configs/multiagent_default.yaml --concurrency 5 --headless
    python running_dirs/run_mind2web.py --config configs/multiagent_default.yaml --resume runs/mind2web/20260211_120000_mind2web
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
	sys.path.insert(0, project_root)

logger = logging.getLogger('mind2web.runner')


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description='Run the Online-Mind2Web benchmark with multi-agent orchestration.',
	)
	parser.add_argument(
		'--config',
		type=str,
		required=True,
		help='Path to the multi-agent YAML config file.',
	)
	parser.add_argument(
		'--concurrency',
		type=int,
		default=3,
		help='Maximum number of tasks to run in parallel (default: 3).',
	)
	parser.add_argument(
		'--headless',
		action='store_true',
		default=False,
		help='Run browsers in headless mode.',
	)
	parser.add_argument(
		'--max-steps',
		type=int,
		default=None,
		help='Override max_steps from config for each task.',
	)
	parser.add_argument(
		'--log-dir',
		type=str,
		default='runs/mind2web',
		help='Base directory for benchmark results (default: runs/mind2web).',
	)
	parser.add_argument(
		'--resume',
		type=str,
		default=None,
		help='Path to a previous run directory to resume from (skips completed tasks).',
	)
	parser.add_argument(
		'--task-ids',
		type=str,
		nargs='*',
		default=None,
		help='Only run specific task IDs (space-separated). Runs all if omitted.',
	)
	parser.add_argument(
		'--max-tasks',
		type=int,
		default=None,
		help='Limit the number of tasks to run (useful for testing).',
	)
	parser.add_argument(
		'--timeout',
		type=int,
		default=600,
		help='Timeout in seconds per task (default: 600 = 10 minutes).',
	)
	parser.add_argument(
		'--log-level',
		type=str,
		default='INFO',
		choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
		help='Log level (default: INFO).',
	)
	parser.add_argument(
		'--hf-token',
		type=str,
		default=None,
		help='HuggingFace token for gated datasets. Can also set HF_TOKEN env var.',
	)
	return parser.parse_args()


def load_mind2web_dataset(hf_token: str | None = None) -> list[dict[str, Any]]:
	"""Load the Online-Mind2Web dataset from HuggingFace.

	This is a gated dataset — you need to accept the terms on HuggingFace
	and provide a token via --hf-token or the HF_TOKEN environment variable.

	Returns a list of dicts with keys: task_id, website, task_description, reference_length.
	Note: The dataset's 'confirmed_task' key is automatically mapped to 'task_description'.
	"""
	try:
		from datasets import load_dataset
	except ImportError:
		logger.error(
			'The `datasets` library is required. Install it with: uv pip install datasets'
		)
		sys.exit(1)

	token = hf_token or os.environ.get('HF_TOKEN')
	if token:
		logger.info('Using provided HuggingFace token for gated dataset access')
	else:
		logger.info(
			'No HF token provided. If the dataset is gated, set --hf-token or HF_TOKEN env var. '
			'You must also accept the dataset terms at https://huggingface.co/datasets/osunlp/Online-Mind2Web'
		)

	logger.info('Loading Online-Mind2Web dataset from HuggingFace...')
	ds = load_dataset('osunlp/Online-Mind2Web', token=token)

	# The dataset may have a single split or train/test splits
	if isinstance(ds, dict):
		# Use the first available split
		split_name = list(ds.keys())[0]
		logger.info(f'Using split: {split_name} ({len(ds[split_name])} tasks)')
		data = [dict(row) for row in ds[split_name]]
	else:
		data = [dict(row) for row in ds]

	# Normalize keys: the dataset uses 'confirmed_task' but we use 'task_description'
	for row in data:
		if 'confirmed_task' in row and 'task_description' not in row:
			row['task_description'] = row['confirmed_task']

	logger.info(f'Loaded {len(data)} tasks from Online-Mind2Web')
	return data


def get_completed_task_ids(resume_dir: str | Path) -> set[str]:
	"""Scan a previous run directory for completed task results."""
	resume_path = Path(resume_dir)
	completed = set()

	results_dir = resume_path / 'task_results'
	if not results_dir.exists():
		return completed

	for result_file in results_dir.glob('*.json'):
		try:
			data = json.loads(result_file.read_text(encoding='utf-8'))
			if data.get('status') == 'completed':
				completed.add(data['task_id'])
		except (json.JSONDecodeError, KeyError):
			continue

	return completed


class Mind2WebBenchmark:
	"""Manages parallel execution of Mind2Web tasks with the multi-agent orchestrator."""

	def __init__(self, args: argparse.Namespace) -> None:
		self.args = args
		self.semaphore = asyncio.Semaphore(args.concurrency)

		# Set up benchmark run directory
		timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
		self.run_dir = Path(args.log_dir) / f'{timestamp}_mind2web'
		self.task_results_dir = self.run_dir / 'task_results'
		self.task_logs_dir = self.run_dir / 'task_logs'

		self.run_dir.mkdir(parents=True, exist_ok=True)
		self.task_results_dir.mkdir(exist_ok=True)
		self.task_logs_dir.mkdir(exist_ok=True)

		# Track results
		self.results: list[dict[str, Any]] = []
		self._results_lock = asyncio.Lock()
		self._shutdown = False

	async def run_single_task(
		self,
		task_data: dict[str, Any],
		config_path: str,
		task_index: int,
		total_tasks: int,
	) -> dict[str, Any]:
		"""Run a single Mind2Web task through the multi-agent orchestrator."""
		from browser_use.browser.profile import BrowserProfile
		from multiagent.config import load_config
		from multiagent.orchestrator import MultiAgentOrchestrator

		task_id = task_data['task_id']
		website = task_data['website']
		task_desc = task_data['task_description']
		ref_length = task_data['reference_length']

		result: dict[str, Any] = {
			'task_id': task_id,
			'website': website,
			'task_description': task_desc,
			'reference_length': ref_length,
			'status': 'pending',
			'start_time': None,
			'end_time': None,
			'duration_seconds': None,
			'steps_taken': None,
			'is_done': None,
			'is_successful': None,
			'final_result': None,
			'errors': [],
		}

		async with self.semaphore:
			if self._shutdown:
				result['status'] = 'skipped'
				return result

			logger.info(
				f'[{task_index + 1}/{total_tasks}] Starting task {task_id}: '
				f'{task_desc[:80]}... (website: {website})'
			)
			result['start_time'] = datetime.now(timezone.utc).isoformat()
			start_time = time.monotonic()

			try:
				# Each task gets its own config instance and browser profile
				config = load_config(config_path)

				if self.args.max_steps is not None:
					config.orchestrator.max_steps = self.args.max_steps

				# Override logging to use per-task subdirectory
				config.logging.run_dir_base = str(self.task_logs_dir)
				config.logging.experiment_name = f'task_{task_id}'

				# Isolated browser profile per task
				browser_profile = BrowserProfile(
					headless=self.args.headless,
				)

				# Prepend website URL to the task description so the agent knows where to go
				full_task = f'Go to {website} and complete the following task: {task_desc}'

				orchestrator = MultiAgentOrchestrator(
					task=full_task,
					config=config,
					config_path=config_path,
					browser_profile=browser_profile,
				)

				# Run with timeout
				agent_result = await asyncio.wait_for(
					orchestrator.run(),
					timeout=self.args.timeout,
				)

				elapsed = time.monotonic() - start_time
				result.update({
					'status': 'completed',
					'end_time': datetime.now(timezone.utc).isoformat(),
					'duration_seconds': round(elapsed, 2),
					'steps_taken': len(agent_result.history),
					'is_done': agent_result.is_done(),
					'is_successful': agent_result.is_successful(),
					'final_result': agent_result.final_result(),
					'errors': [e for e in agent_result.errors() if e],
					'log_dir': str(orchestrator.run_logger.run_dir),
				})

				status_str = 'SUCCESS' if agent_result.is_successful() else 'DONE' if agent_result.is_done() else 'INCOMPLETE'
				logger.info(
					f'[{task_index + 1}/{total_tasks}] Task {task_id} {status_str} '
					f'in {elapsed:.1f}s ({len(agent_result.history)} steps)'
				)

			except asyncio.TimeoutError:
				elapsed = time.monotonic() - start_time
				result.update({
					'status': 'timeout',
					'end_time': datetime.now(timezone.utc).isoformat(),
					'duration_seconds': round(elapsed, 2),
					'errors': [f'Task timed out after {self.args.timeout}s'],
				})
				logger.warning(
					f'[{task_index + 1}/{total_tasks}] Task {task_id} TIMEOUT after {elapsed:.1f}s'
				)

			except Exception as e:
				elapsed = time.monotonic() - start_time
				result.update({
					'status': 'error',
					'end_time': datetime.now(timezone.utc).isoformat(),
					'duration_seconds': round(elapsed, 2),
					'errors': [str(e)],
				})
				logger.error(
					f'[{task_index + 1}/{total_tasks}] Task {task_id} ERROR: {e}',
					exc_info=True,
				)

		# Save individual task result
		result_path = self.task_results_dir / f'{task_id}.json'
		result_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')

		# Track aggregate
		async with self._results_lock:
			self.results.append(result)

		return result

	async def run_benchmark(self, tasks: list[dict[str, Any]], config_path: str) -> dict[str, Any]:
		"""Run the full benchmark on all tasks in parallel."""
		total = len(tasks)
		logger.info(f'Starting Mind2Web benchmark: {total} tasks, concurrency={self.args.concurrency}')

		# Save benchmark metadata
		meta = {
			'total_tasks': total,
			'concurrency': self.args.concurrency,
			'config_path': config_path,
			'headless': self.args.headless,
			'max_steps': self.args.max_steps,
			'timeout': self.args.timeout,
			'start_time': datetime.now(timezone.utc).isoformat(),
		}
		(self.run_dir / 'benchmark_meta.json').write_text(
			json.dumps(meta, indent=2), encoding='utf-8'
		)

		# Set up graceful shutdown on SIGINT/SIGTERM
		loop = asyncio.get_event_loop()
		for sig in (signal.SIGINT, signal.SIGTERM):
			loop.add_signal_handler(sig, self._handle_shutdown)

		# Launch all tasks concurrently (semaphore controls actual parallelism)
		coros = [
			self.run_single_task(task, config_path, i, total)
			for i, task in enumerate(tasks)
		]
		await asyncio.gather(*coros, return_exceptions=True)

		# Generate summary
		summary = self._generate_summary(total)
		summary_path = self.run_dir / 'benchmark_summary.json'
		summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')

		return summary

	def _handle_shutdown(self) -> None:
		"""Handle graceful shutdown on SIGINT/SIGTERM."""
		if self._shutdown:
			logger.warning('Forced shutdown - exiting immediately')
			sys.exit(1)
		logger.warning('Shutdown signal received. Completing in-progress tasks, skipping remaining...')
		self._shutdown = True

	def _generate_summary(self, total_tasks: int) -> dict[str, Any]:
		"""Generate aggregate benchmark summary statistics."""
		completed = [r for r in self.results if r['status'] == 'completed']
		successful = [r for r in completed if r.get('is_successful')]
		timed_out = [r for r in self.results if r['status'] == 'timeout']
		errored = [r for r in self.results if r['status'] == 'error']
		skipped = [r for r in self.results if r['status'] == 'skipped']

		durations = [r['duration_seconds'] for r in completed if r['duration_seconds'] is not None]
		steps = [r['steps_taken'] for r in completed if r['steps_taken'] is not None]

		summary: dict[str, Any] = {
			'total_tasks': total_tasks,
			'completed': len(completed),
			'successful': len(successful),
			'timed_out': len(timed_out),
			'errored': len(errored),
			'skipped': len(skipped),
			'success_rate': round(len(successful) / max(len(completed), 1) * 100, 2),
			'completion_rate': round(len(completed) / max(total_tasks, 1) * 100, 2),
			'avg_duration_seconds': round(sum(durations) / max(len(durations), 1), 2) if durations else None,
			'avg_steps': round(sum(steps) / max(len(steps), 1), 2) if steps else None,
			'median_duration_seconds': round(sorted(durations)[len(durations) // 2], 2) if durations else None,
			'median_steps': round(sorted(steps)[len(steps) // 2], 2) if steps else None,
			'end_time': datetime.now(timezone.utc).isoformat(),
			'run_dir': str(self.run_dir),
		}

		# Per-website breakdown
		website_stats: dict[str, dict[str, int]] = {}
		for r in self.results:
			site = r.get('website', 'unknown')
			if site not in website_stats:
				website_stats[site] = {'total': 0, 'completed': 0, 'successful': 0}
			website_stats[site]['total'] += 1
			if r['status'] == 'completed':
				website_stats[site]['completed'] += 1
			if r.get('is_successful'):
				website_stats[site]['successful'] += 1

		summary['per_website'] = website_stats

		return summary


async def main() -> None:
	args = parse_args()

	logging.basicConfig(
		level=getattr(logging, args.log_level.upper(), logging.INFO),
		format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
	)

	# Load dataset
	tasks = load_mind2web_dataset(hf_token=args.hf_token)

	# Filter by task IDs if specified
	if args.task_ids:
		task_id_set = set(args.task_ids)
		tasks = [t for t in tasks if t['task_id'] in task_id_set]
		logger.info(f'Filtered to {len(tasks)} tasks by task_ids')

	# Resume: skip already-completed tasks
	if args.resume:
		completed_ids = get_completed_task_ids(args.resume)
		before = len(tasks)
		tasks = [t for t in tasks if t['task_id'] not in completed_ids]
		logger.info(f'Resuming: skipped {before - len(tasks)} already-completed tasks, {len(tasks)} remaining')

	# Limit task count if specified
	if args.max_tasks is not None:
		tasks = tasks[: args.max_tasks]
		logger.info(f'Limited to {len(tasks)} tasks')

	if not tasks:
		logger.info('No tasks to run. Exiting.')
		return

	# Run benchmark
	benchmark = Mind2WebBenchmark(args)
	summary = await benchmark.run_benchmark(tasks, args.config)

	# Print summary
	_log_summary(summary)


def _log_summary(summary: dict[str, Any]) -> None:
	"""Print a formatted benchmark summary."""
	print('\n' + '=' * 70)
	print('MIND2WEB BENCHMARK COMPLETE')
	print('=' * 70)
	print(f"  Total tasks:       {summary['total_tasks']}")
	print(f"  Completed:         {summary['completed']}")
	print(f"  Successful:        {summary['successful']}")
	print(f"  Timed out:         {summary['timed_out']}")
	print(f"  Errored:           {summary['errored']}")
	print(f"  Skipped:           {summary['skipped']}")
	print(f"  Success rate:      {summary['success_rate']}%")
	print(f"  Completion rate:   {summary['completion_rate']}%")
	if summary['avg_duration_seconds'] is not None:
		print(f"  Avg duration:      {summary['avg_duration_seconds']}s")
	if summary['avg_steps'] is not None:
		print(f"  Avg steps:         {summary['avg_steps']}")
	if summary['median_duration_seconds'] is not None:
		print(f"  Median duration:   {summary['median_duration_seconds']}s")
	if summary['median_steps'] is not None:
		print(f"  Median steps:      {summary['median_steps']}")
	print(f"  Results dir:       {summary['run_dir']}")
	print('=' * 70)


if __name__ == '__main__':
	asyncio.run(main())
