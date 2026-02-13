# Runners Directory

This directory contains generic, reusable runner scripts for executing multi-agent experiments.

## Files

### `multiagent_runner.py`
Generic runner for single multi-agent tasks.

**Usage** (typically called from experiment `run.sh`):
```bash
python runners/multiagent_runner.py \
    --config experiments/my_experiment/config.yaml \
    --task "Search for something" \
    --headless \
    --max-steps 30
```

**Arguments**:
- `--config`: Path to experiment config YAML
- `--task`: Task instruction string
- `--headless`: Run browser in headless mode (optional)
- `--max-steps`: Override max_steps from config (optional)
- `--log-level`: Override log level (DEBUG/INFO/WARNING/ERROR)
- `--log-dir`: Override log directory


### `matrix_runner.py`
Generic runner for matrix-style experiments (prompt/workflow combinational testing).

**Usage** (typically called from experiment `run.sh`):
```bash
python runners/matrix_runner.py     --matrix experiments/multiagent_matrix_v1/matrix.yaml     --group smoke     --dry-run
```

**Arguments**:
- `--matrix`: Path to matrix definition YAML
- `--group`: Run group key in matrix config (default: smoke)
- `--dry-run`: Expand matrix and print plan only
- `--execute`: Execute all expanded runs
- `--headless`: Pass headless mode to each expanded run
- `--max-steps`: Override max_steps for each expanded run

### `mind2web_runner.py`
Generic runner for Mind2Web benchmark suite.

**Usage** (typically called from experiment `run_benchmark.sh`):
```bash
python runners/mind2web_runner.py \
    --config experiments/mind2web_baseline/config.yaml \
    --concurrency 3 \
    --headless \
    --max-tasks 10
```

**Arguments**:
- `--config`: Path to experiment config YAML
- `--concurrency`: Number of parallel tasks (default: 3)
- `--headless`: Run browsers in headless mode
- `--max-steps`: Override max_steps for each task
- `--max-tasks`: Limit number of tasks to run
- `--timeout`: Timeout per task in seconds (default: 600)
- `--log-level`: Log verbosity
- `--log-dir`: Base directory for results
- `--resume`: Resume from previous run directory
- `--task-ids`: Only run specific task IDs
- `--hf-token`: HuggingFace token for dataset access

## Important: Don't Edit These Files for Experiments!

These runners are **generic** and **reusable** across all experiments.

### ✅ DO:
- Call these from experiment `run.sh` scripts
- Pass experiment-specific settings via `--config`
- Use command-line arguments for runtime overrides

### ❌ DON'T:
- Hardcode experiment-specific settings here
- Create experiment-specific variations of these files
- Modify these files for one-off experiments

## How Experiments Use Runners

Each experiment has a `run.sh` script that calls these runners:

```bash
# experiments/my_experiment/run.sh
CONFIG="$SCRIPT_DIR/config.yaml"
cd "$PROJECT_ROOT"
python runners/multiagent_runner.py --config "$CONFIG" --task "$TASK"
```

This pattern ensures:
- Runners stay generic and reusable
- Experiment settings are documented in experiment folders
- Easy to compare experiments by comparing their configs

## Creating New Runners

If you need a new type of runner (e.g., for a different benchmark):

1. **Copy existing runner** as template:
   ```bash
   cp multiagent_runner.py new_benchmark_runner.py
   ```

2. **Make it generic**:
   - Accept `--config` for experiment settings
   - Use command-line args for runtime overrides
   - Don't hardcode experiment-specific values

3. **Document usage** in this README

4. **Create experiment** that uses it:
   ```bash
   mkdir experiments/new_benchmark_baseline
   # Create config.yaml and run.sh that call your runner
   ```

## See Also

- `EXPERIMENTS.md`: Complete guide to experiment structure
- `experiments/README.md`: How to create experiments
- `experiments/baseline_qwen3vl/run.sh`: Example of calling a runner
