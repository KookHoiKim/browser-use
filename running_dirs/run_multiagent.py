#!/usr/bin/env python3
"""Deprecated compatibility wrapper for the multi-agent runner.

Canonical entrypoint:
    python runners/multiagent_runner.py --config ... --task "..."
"""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == '__main__':
	runner_path = Path(__file__).resolve().parent.parent / 'runners' / 'multiagent_runner.py'
	runpy.run_path(str(runner_path), run_name='__main__')
