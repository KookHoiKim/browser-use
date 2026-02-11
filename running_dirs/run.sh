#!/bin/bash

# Multiagent Browser-Use Runner
# Edit the hardcoded parameters below and run this script directly

# ============================================================
# HARDCODED PARAMETERS - Edit these for your experiment
# ============================================================
CONFIG="configs/multiagent_default.yaml"
TASK="Search for the latest Python release"
HEADLESS=false          # Set to true for headless mode
MAX_STEPS=""            # e.g., "10" or leave empty for config default
LOG_LEVEL=""            # e.g., "DEBUG", "INFO", "WARNING", "ERROR" or leave empty
LOG_DIR=""              # e.g., "my_logs" or leave empty for config default

# ============================================================
# Script Logic - No need to edit below unless changing behavior
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

# Find run_multiagent.py relative to script directory
RUN_SCRIPT="$SCRIPT_DIR/run_multiagent.py"
if [[ ! -f "$RUN_SCRIPT" ]]; then
	# Try in running_dirs subdirectory of project root
	RUN_SCRIPT="$PROJECT_ROOT/running_dirs/run_multiagent.py"
fi

if [[ ! -f "$RUN_SCRIPT" ]]; then
	echo "Error: Could not find run_multiagent.py"
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
