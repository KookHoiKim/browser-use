#!/bin/bash

# =============================================================================
# Experiment: Baseline Qwen3VL Multi-Agent
# =============================================================================
# Purpose: Establish baseline performance with standard multi-agent configuration
# Date: 2026-02-12
# Model: Qwen3VL_32b via vLLM
# Agents: Planner, Searcher, Critic (all enabled)
# Prompts: Using default prompts from shared/prompts/
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Experiment configuration
EXPERIMENT_NAME="baseline_qwen3vl"
CONFIG="$SCRIPT_DIR/config.yaml"

# Task can be provided as first argument or use default
TASK="${1:-Search for the latest Python release}"

# Optional environment variables
HEADLESS="${HEADLESS:-false}"
MAX_STEPS="${MAX_STEPS:-}"
LOG_LEVEL="${LOG_LEVEL:-}"

# Build command arguments
CMD_ARGS=(
	"--config" "$CONFIG"
	"--task" "$TASK"
)

if [[ "$HEADLESS" == "true" ]]; then
	CMD_ARGS+=("--headless")
fi

if [[ -n "$MAX_STEPS" ]]; then
	CMD_ARGS+=("--max-steps" "$MAX_STEPS")
fi

if [[ -n "$LOG_LEVEL" ]]; then
	CMD_ARGS+=("--log-level" "$LOG_LEVEL")
fi

# Print configuration for transparency
echo "=========================================="
echo "Experiment: $EXPERIMENT_NAME"
echo "=========================================="
echo "Config:     $CONFIG"
echo "Task:       $TASK"
echo "Headless:   $HEADLESS"
echo "Project:    $PROJECT_ROOT"
echo "=========================================="
echo ""

# Execute from project root (so imports work correctly)
cd "$PROJECT_ROOT" || exit 1
python runners/multiagent_runner.py "${CMD_ARGS[@]}"
