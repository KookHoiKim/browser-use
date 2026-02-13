#!/bin/bash

# =============================================================================
# Experiment: Multi-Agent Matrix v1
# =============================================================================
# Purpose: Systematically compare prompt variants and agent workflow variants
# Base config: shared/configs/multiagent_default.yaml
# Runner: runners/matrix_runner.py (generic runner)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MATRIX_PATH="experiments/multiagent_matrix_v1/matrix.yaml"
GROUP="${GROUP:-smoke}"
HEADLESS="${HEADLESS:-true}"
MAX_STEPS="${MAX_STEPS:-}"
DRY_RUN="${DRY_RUN:-false}"

CMD_ARGS=(
  "--matrix" "$MATRIX_PATH"
  "--group" "$GROUP"
)

if [[ "$DRY_RUN" == "true" ]]; then
  CMD_ARGS+=("--dry-run")
else
  CMD_ARGS+=("--execute")
fi

if [[ "$HEADLESS" == "true" ]]; then
  CMD_ARGS+=("--headless")
fi

if [[ -n "$MAX_STEPS" ]]; then
  CMD_ARGS+=("--max-steps" "$MAX_STEPS")
fi

echo "=========================================="
echo "Experiment: multiagent_matrix_v1"
echo "=========================================="
echo "Matrix:     $MATRIX_PATH"
echo "Group:      $GROUP"
echo "Dry run:    $DRY_RUN"
echo "Headless:   $HEADLESS"
echo "Project:    $PROJECT_ROOT"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT" || exit 1
python runners/matrix_runner.py "${CMD_ARGS[@]}"
