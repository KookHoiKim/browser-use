#!/bin/bash

# =============================================================================
# Experiment: Mind2Web Baseline Benchmark
# =============================================================================
# Purpose: Benchmark multi-agent system on Mind2Web dataset
# Date: 2026-02-12
# Dataset: osunlp/Online-Mind2Web (HuggingFace)
# Usage:
#   ./run_benchmark.sh                    # Run all tasks (default 3 concurrent)
#   ./run_benchmark.sh --concurrency 5    # Run with 5 concurrent tasks
#   ./run_benchmark.sh --max-tasks 10     # Test with first 10 tasks only
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Experiment configuration
EXPERIMENT_NAME="mind2web_baseline"
CONFIG="$SCRIPT_DIR/config.yaml"

# Default benchmark settings
CONCURRENCY="${CONCURRENCY:-3}"
HEADLESS="${HEADLESS:-true}"
MAX_TASKS="${MAX_TASKS:-}"
TIMEOUT="${TIMEOUT:-600}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Build command arguments
CMD_ARGS=(
	"--config" "$CONFIG"
	"--concurrency" "$CONCURRENCY"
	"--timeout" "$TIMEOUT"
	"--log-level" "$LOG_LEVEL"
)

if [[ "$HEADLESS" == "true" ]]; then
	CMD_ARGS+=("--headless")
fi

if [[ -n "$MAX_TASKS" ]]; then
	CMD_ARGS+=("--max-tasks" "$MAX_TASKS")
fi

# Pass through any additional arguments
CMD_ARGS+=("$@")

# Print configuration for transparency
echo "=========================================="
echo "Benchmark: $EXPERIMENT_NAME"
echo "=========================================="
echo "Config:      $CONFIG"
echo "Concurrency: $CONCURRENCY"
echo "Headless:    $HEADLESS"
echo "Timeout:     ${TIMEOUT}s per task"
echo "Max tasks:   ${MAX_TASKS:-all}"
echo "Project:     $PROJECT_ROOT"
echo "=========================================="
echo ""
echo "Note: This will run the Mind2Web benchmark"
echo "      Make sure you have:"
echo "      1. Accepted dataset terms at:"
echo "         https://huggingface.co/datasets/osunlp/Online-Mind2Web"
echo "      2. Set HF_TOKEN env var or use --hf-token"
echo ""
echo "Press Ctrl+C to cancel within 5 seconds..."
sleep 5
echo ""

# Execute from project root (so imports work correctly)
cd "$PROJECT_ROOT" || exit 1
python runners/mind2web_runner.py "${CMD_ARGS[@]}"
