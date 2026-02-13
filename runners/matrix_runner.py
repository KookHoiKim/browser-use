#!/usr/bin/env python3
"""Generic runner for matrix-style multi-agent experiments.

This runner expands prompt/workflow combinations into concrete config files,
then optionally executes each run through runners/multiagent_runner.py.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class PromptVariant(BaseModel):
    """Prompt path overrides for planner/searcher/critic."""

    model_config = ConfigDict(extra='forbid')

    planner_prompt_path: str
    searcher_prompt_path: str
    critic_prompt_path: str


class WorkflowVariant(BaseModel):
    """Agent enable flags and orchestration policy overrides."""

    model_config = ConfigDict(extra='forbid')

    planner_enabled: bool = True
    searcher_enabled: bool = True
    critic_enabled: bool = True
    always_use_critic: bool = True
    searcher_on_first_step: bool = True


class RunGroup(BaseModel):
    """Subset of matrix dimensions that should be executed together."""

    model_config = ConfigDict(extra='forbid')

    task_set: str
    prompt_variants: list[str] = Field(min_length=1)
    workflow_variants: list[str] = Field(min_length=1)


class MatrixConfig(BaseModel):
    """Top-level matrix experiment definition."""

    model_config = ConfigDict(extra='forbid')

    base_config: str
    generated_config_dir: str
    results_dir: str
    task_sets: dict[str, list[str]]
    prompt_variants: dict[str, PromptVariant]
    workflow_variants: dict[str, WorkflowVariant]
    run_groups: dict[str, RunGroup]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run combinational multi-agent experiments.')
    parser.add_argument('--matrix', required=True, help='Path to matrix YAML')
    parser.add_argument(
        '--group',
        default='smoke',
        help='Run group from matrix YAML (default: smoke).',
    )
    parser.add_argument('--dry-run', action='store_true', help='Print expanded run plan only.')
    parser.add_argument('--execute', action='store_true', help='Execute expanded run plan.')
    parser.add_argument('--headless', action='store_true', help='Pass --headless to each run.')
    parser.add_argument('--max-steps', type=int, default=None, help='Override max steps for all runs.')
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with path.open(encoding='utf-8') as file:
        return yaml.safe_load(file)


def apply_variant(
    base_config: dict,
    prompt_variant: PromptVariant,
    workflow_variant: WorkflowVariant,
    run_id: str,
    results_dir: str,
) -> dict:
    """Build a run-specific config from base + prompt/workflow overrides."""
    config = copy.deepcopy(base_config)

    config['agents']['planner']['enabled'] = workflow_variant.planner_enabled
    config['agents']['searcher']['enabled'] = workflow_variant.searcher_enabled
    config['agents']['critic']['enabled'] = workflow_variant.critic_enabled

    config['agents']['planner']['prompt_path'] = prompt_variant.planner_prompt_path
    config['agents']['searcher']['prompt_path'] = prompt_variant.searcher_prompt_path
    config['agents']['critic']['prompt_path'] = prompt_variant.critic_prompt_path

    config['orchestrator']['always_use_critic'] = workflow_variant.always_use_critic
    config['orchestrator']['searcher_on_first_step'] = workflow_variant.searcher_on_first_step

    config['logging']['experiment_name'] = run_id
    config['logging']['run_dir_base'] = results_dir
    return config


def run_command(command: list[str], cwd: Path) -> int:
    result = subprocess.run(command, cwd=cwd, check=False)
    return result.returncode


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    matrix_path = project_root / args.matrix

    matrix = MatrixConfig.model_validate(load_yaml(matrix_path))
    base_config = load_yaml(project_root / matrix.base_config)

    group = matrix.run_groups.get(args.group)
    if group is None:
        available_groups = ', '.join(matrix.run_groups)
        raise ValueError(f'Unknown group: {args.group}. Available groups: {available_groups}')

    generated_config_dir = project_root / matrix.generated_config_dir
    generated_config_dir.mkdir(parents=True, exist_ok=True)

    run_manifest: list[dict[str, str]] = []
    tasks = matrix.task_sets[group.task_set]

    for task_index, task in enumerate(tasks, start=1):
        for prompt_name in group.prompt_variants:
            prompt_variant = matrix.prompt_variants[prompt_name]
            for workflow_name in group.workflow_variants:
                workflow_variant = matrix.workflow_variants[workflow_name]
                run_id = f'{args.group}_t{task_index}_{prompt_name}_{workflow_name}'

                run_config = apply_variant(
                    base_config=base_config,
                    prompt_variant=prompt_variant,
                    workflow_variant=workflow_variant,
                    run_id=run_id,
                    results_dir=matrix.results_dir,
                )

                config_path = generated_config_dir / f'{run_id}.yaml'
                with config_path.open('w', encoding='utf-8') as file:
                    yaml.safe_dump(run_config, file, sort_keys=False, allow_unicode=True)

                run_manifest.append(
                    {
                        'run_id': run_id,
                        'task': task,
                        'config_path': str(config_path.relative_to(project_root)),
                    }
                )

    manifest_path = generated_config_dir / f'{args.group}_manifest.json'
    with manifest_path.open('w', encoding='utf-8') as file:
        json.dump(run_manifest, file, ensure_ascii=False, indent=2)

    print(f'Prepared {len(run_manifest)} runs. Manifest: {manifest_path.relative_to(project_root)}')

    if args.dry_run or not args.execute:
        for run in run_manifest:
            print(f"- {run['run_id']}: {run['config_path']}")
        return

    failed_runs = 0
    for run in run_manifest:
        command = [
            'python',
            'runners/multiagent_runner.py',
            '--config',
            run['config_path'],
            '--task',
            run['task'],
        ]

        if args.headless:
            command.append('--headless')
        if args.max_steps is not None:
            command.extend(['--max-steps', str(args.max_steps)])

        print(f"\n=== Running: {run['run_id']} ===")
        if run_command(command, cwd=project_root) != 0:
            failed_runs += 1
            print(f"Run failed: {run['run_id']}")

    if failed_runs:
        raise SystemExit(f'{failed_runs} runs failed.')


if __name__ == '__main__':
    main()
