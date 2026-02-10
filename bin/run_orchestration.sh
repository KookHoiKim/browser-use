#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bin/run_orchestration.sh [options]

Options:
  -e, --example   Example to run: simple | complex | events | custom (default: simple)
  -c, --config    Path to orchestration config YAML
  -h, --help      Show this help

Examples:
  bin/run_orchestration.sh --example simple
  bin/run_orchestration.sh --example complex --config examples/orchestration_configs/sequence_planner_navigator.yaml
  BROWSER_USE_ORCHESTRATION_CONFIG=examples/orchestration_config.yaml bin/run_orchestration.sh
USAGE
}

example="simple"
config=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--example)
      example="$2"
      shift 2
      ;;
    -c|--config)
      config="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

args=("examples/multi_agent_orchestration.py" "$example")
if [[ -n "$config" ]]; then
  args+=("--config" "$config")
fi

uv run python "${args[@]}"
