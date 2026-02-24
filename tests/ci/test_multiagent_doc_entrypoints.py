"""Guardrails for multi-agent documentation entrypoints.

Ensures documented canonical entrypoints exist to avoid doc/code drift.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_multiagent_readme_uses_canonical_entrypoint() -> None:
	"""README_multiagent should reference only the canonical runner path."""
	readme = (REPO_ROOT / 'README_multiagent.md').read_text(encoding='utf-8')
	assert 'python runners/multiagent_runner.py' in readme
	assert 'scripts/run_multiagent.py' not in readme


def test_documented_multiagent_entrypoints_exist() -> None:
	"""Documented multi-agent entrypoint files must exist."""
	documented_paths = [
		'runners/multiagent_runner.py',
		'running_dirs/run_multiagent.py',
	]

	for rel_path in documented_paths:
		path = REPO_ROOT / rel_path
		assert path.exists(), f'Documented entrypoint does not exist: {rel_path}'
