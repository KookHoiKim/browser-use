#!/bin/bash

# Multiagent Browser-Use Runner
# Supports both external arguments and hardcoded parameters
# External arguments take precedence over hardcoded values
#
# Usage:
#   ./run.sh [--config PATH] [--task "TASK"] [--headless] [--max-steps N] [--log-level LEVEL] [--log-dir DIR]
#
# Examples:
#   ./run.sh --task "Search for Python 3.12 features"
#   ./run.sh --task "Find news" --headless --max-steps 10
#   ./run.sh --config custom.yaml --task "Research AI" --log-dir my_logs

# ============================================================
# HARDCODED PARAMETERS - Edit these for your experiment
# ============================================================
DEFAULT_CONFIG="configs/multiagent_default.yaml"
DEFAULT_TASK="Search for the latest Python release"
DEFAULT_HEADLESS=false          # Set to true for headless mode
DEFAULT_MAX_STEPS=""            # e.g., "10" or leave empty for config default
DEFAULT_LOG_LEVEL=""            # e.g., "DEBUG", "INFO", "WARNING", "ERROR" or leave empty
DEFAULT_LOG_DIR=""              # e.g., "my_logs" or leave empty for script directory

# ============================================================
# Parse External Arguments (takes precedence over hardcoded)
# ============================================================
CONFIG=""
TASK=""
HEADLESS=""
MAX_STEPS=""
LOG_LEVEL=""
LOG_DIR=""

while [[ $# -gt 0 ]]; do
	case $1 in
		--config)
			CONFIG="$2"
			shift 2
			;;
		--task)
			TASK="$2"
			shift 2
			;;
		--headless)
			HEADLESS=true
			shift
			;;
		--max-steps)
			MAX_STEPS="$2"
			shift 2
			;;
		--log-level)
			LOG_LEVEL="$2"
			shift 2
			;;
		--log-dir)
			LOG_DIR="$2"
			shift 2
			;;
		*)
			echo "Unknown argument: $1"
			echo "Usage: $0 [--config PATH] [--task TASK] [--headless] [--max-steps N] [--log-level LEVEL] [--log-dir DIR]"
			exit 1
			;;
	esac
done

# ============================================================
# Apply Defaults (external args > hardcoded > fallback defaults)
# ============================================================

# Get script directory (this is the experiment directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Find project root by looking for pyproject.toml
PROJECT_ROOT="$SCRIPT_DIR"
while [[ "$PROJECT_ROOT" != "/" ]]; do
	if [[ -f "$PROJECT_ROOT/pyproject.toml" ]]; then
		break
	fi
	PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
	echo "Error: Could not find project root (no pyproject.toml found)"
	exit 1
fi

# Apply priority: external arg > hardcoded > fallback default
CONFIG="${CONFIG:-$DEFAULT_CONFIG}"
TASK="${TASK:-$DEFAULT_TASK}"
if [[ -z "$HEADLESS" ]]; then
	HEADLESS="$DEFAULT_HEADLESS"
fi
MAX_STEPS="${MAX_STEPS:-$DEFAULT_MAX_STEPS}"
LOG_LEVEL="${LOG_LEVEL:-$DEFAULT_LOG_LEVEL}"
LOG_DIR="${LOG_DIR:-$DEFAULT_LOG_DIR}"

# If log_dir is still empty, default to script directory
if [[ -z "$LOG_DIR" ]]; then
	LOG_DIR="$SCRIPT_DIR"
fi

# Resolve relative config path from script directory
if [[ "$CONFIG" != /* ]]; then
	# If config is relative, try from script dir first, then project root
	if [[ -f "$SCRIPT_DIR/$CONFIG" ]]; then
		CONFIG="$SCRIPT_DIR/$CONFIG"
	elif [[ -f "$PROJECT_ROOT/$CONFIG" ]]; then
		CONFIG="$PROJECT_ROOT/$CONFIG"
	fi
fi

# Build command arguments array
CMD_ARGS=(
	"--config" "$CONFIG"
	"--task" "$TASK"
)

if [[ "$HEADLESS" == true ]]; then
	CMD_ARGS+=("--headless")
fi

if [[ -n "$MAX_STEPS" ]]; then
	CMD_ARGS+=("--max-steps" "$MAX_STEPS")
fi

if [[ -n "$LOG_LEVEL" ]]; then
	CMD_ARGS+=("--log-level" "$LOG_LEVEL")
fi

if [[ -n "$LOG_DIR" ]]; then
	CMD_ARGS+=("--log-dir" "$LOG_DIR")
fi

# Canonical multi-agent runner path
RUN_SCRIPT="$PROJECT_ROOT/runners/multiagent_runner.py"

if [[ ! -f "$RUN_SCRIPT" ]]; then
	echo "Error: Could not find runners/multiagent_runner.py"
	exit 1
fi

# Print command for transparency
echo "Experiment dir: $SCRIPT_DIR"
echo "Project root:   $PROJECT_ROOT"
echo "Running: python $RUN_SCRIPT ${CMD_ARGS[@]}"
echo ""

# Execute from project root (so imports work correctly)
cd "$PROJECT_ROOT" || exit 1
python "$RUN_SCRIPT" "${CMD_ARGS[@]}"
