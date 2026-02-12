# Experiment Structure Guide

This document describes the experiment-centric directory structure for running multi-agent browser-use experiments.

## Overview

The project uses a modular structure that separates reusable code, shared resources, and individual experiments:

```
browser-use/
├── runners/              # Reusable execution scripts
├── experiments/          # Individual experiment configurations
├── shared/              # Shared prompts and configs
└── results/             # Auto-generated experiment results
```

## Directory Structure

### `runners/` - Reusable Execution Code

Contains generic runner scripts that execute experiments based on configuration:

- `multiagent_runner.py`: Runs single multi-agent tasks
- `mind2web_runner.py`: Runs Mind2Web benchmark suite

**Key principle**: These are generic runners. Experiment-specific settings live in `experiments/`, not here.

### `experiments/` - Experiment Configurations

Each experiment is a self-contained directory with:

```
experiments/
├── baseline_qwen3vl/
│   ├── config.yaml          # Experiment config
│   ├── run.sh               # Execution script (documents settings)
│   └── prompts/             # (optional) Custom prompts
│       └── planner.md
├── no_critic_experiment/
│   ├── config.yaml
│   └── run.sh
└── custom_prompts_v1/
    ├── config.yaml
    ├── run.sh
    └── prompts/
        └── planner.md
```

**Benefits**:
- ✅ **Reproducibility**: `run.sh` shows exactly what settings were used
- ✅ **Transparency**: Config and prompts are visible in experiment folder
- ✅ **Easy comparison**: `diff experiment1/ experiment2/` shows differences
- ✅ **Version control**: Git tracks experiment configurations over time

### `shared/` - Common Resources

Shared resources used across experiments:

```
shared/
├── prompts/              # Default prompt templates
│   ├── planner.md
│   ├── searcher.md
│   └── critic.md
└── configs/              # Base configuration templates
    ├── multiagent_default.yaml
    └── mind2web_benchmark.yaml
```

**Usage**:
- Experiments reference `shared/prompts/` by default
- Override by creating custom prompts in `experiments/<name>/prompts/`

### `results/` - Auto-Generated Results

Experiments automatically save results here:

```
results/
├── baseline_qwen3vl_20260212_103045/
│   ├── run.log
│   ├── screenshots/
│   └── dom_snapshots/
└── no_critic_experiment_20260212_141522/
    └── ...
```

**Note**: This directory is auto-created and typically git-ignored.

## Running Experiments

### Quick Start

```bash
# Run baseline experiment
cd experiments/baseline_qwen3vl
./run.sh "Search for the latest Python release"

# Run with environment variables
HEADLESS=true MAX_STEPS=30 ./run.sh "Your task"
```

### Creating a New Experiment

1. **Copy existing experiment**:
   ```bash
   cp -r experiments/baseline_qwen3vl experiments/my_experiment
   cd experiments/my_experiment
   ```

2. **Edit `config.yaml`**:
   ```yaml
   logging:
     experiment_name: my_experiment  # Update this

   agents:
     planner:
       provider:
         temperature: 0.5  # Change settings
   ```

3. **Update `run.sh` header**:
   ```bash
   # =============================================================================
   # Experiment: My Experiment
   # =============================================================================
   # Purpose: Test higher temperature for more creative planning
   # Changes: planner.temperature = 0.5 (baseline: 0.2)
   # =============================================================================
   ```

4. **Add custom prompts (optional)**:
   ```bash
   mkdir prompts
   cp ../../shared/prompts/planner.md prompts/
   # Edit prompts/planner.md

   # Update config.yaml:
   # prompt_path: experiments/my_experiment/prompts/planner.md
   ```

5. **Run it**:
   ```bash
   ./run.sh "Test task"
   ```

## Experiment Workflow

### 1. Baseline Establishment
```bash
cd experiments/baseline_qwen3vl
./run.sh "Task 1"
./run.sh "Task 2"
./run.sh "Task 3"
# Review results/ to establish baseline metrics
```

### 2. Hypothesis Testing
```bash
# Create experiment to test hypothesis
cp -r baseline_qwen3vl higher_temperature
cd higher_temperature
# Edit config.yaml: temperature: 0.2 → 0.5
./run.sh "Task 1"  # Run same tasks
./run.sh "Task 2"
./run.sh "Task 3"
```

### 3. Result Comparison
```bash
# Compare configs
diff baseline_qwen3vl/config.yaml higher_temperature/config.yaml

# Compare results
ls -la ../../results/baseline_qwen3vl_*/
ls -la ../../results/higher_temperature_*/

# Analyze logs
grep "SUCCESS\|FAILED" ../../results/*/run.log
```

## Best Practices

### ✅ DO:
- **One variable per experiment**: Change one thing at a time for clear attribution
- **Document in run.sh**: Explain what's different and why in script comments
- **Meaningful names**: `high_temp_test` > `experiment_1`
- **Version control**: Commit experiment configs to Git
- **Track metrics**: Keep notes on success rates, steps taken, errors

### ❌ DON'T:
- **Don't modify runners/**: Keep runner code generic, put settings in experiments/
- **Don't hardcode in code**: Use config files and environment variables
- **Don't reuse experiment folders**: Create new folders for new experiments
- **Don't forget to document**: Future you will thank you

## Example: Comparing Critic Impact

```bash
# 1. Baseline (with critic)
cd experiments/baseline_qwen3vl
./run.sh "Find Python 3.12 release date" > ../../results/baseline.txt

# 2. No critic
cd ../no_critic_experiment
./run.sh "Find Python 3.12 release date" > ../../results/no_critic.txt

# 3. Compare
diff ../../results/baseline.txt ../../results/no_critic.txt
# Check: steps taken, execution time, success rate
```

## Environment Variables

All experiments support:

```bash
HEADLESS=true        # Run browser headlessly
MAX_STEPS=30         # Override max steps
LOG_LEVEL=DEBUG      # Set verbosity
HF_TOKEN=xxx         # For Mind2Web benchmark
```

## Migration from Old Structure

If you have old `running_dirs/` experiments:

1. **Create new experiment folder**:
   ```bash
   mkdir -p experiments/my_old_experiment
   ```

2. **Move config if you had one**:
   ```bash
   cp old_config.yaml experiments/my_old_experiment/config.yaml
   ```

3. **Create run.sh based on template**:
   ```bash
   cp experiments/baseline_qwen3vl/run.sh experiments/my_old_experiment/
   # Edit to match your old settings
   ```

## Troubleshooting

### Import errors
```bash
# Make sure you're running from project root
cd /path/to/browser-use
python runners/multiagent_runner.py ...
```

### Config not found
```bash
# Use absolute paths or ensure config.yaml is in experiment folder
cd experiments/my_experiment
cat config.yaml  # Verify it exists
```

### Results not saving
```bash
# Check results/ directory exists
mkdir -p results
# Check config.yaml logging section
grep "run_dir_base" config.yaml
```

## See Also

- `experiments/README.md`: Detailed guide for experiments directory
- `shared/configs/`: Base configuration templates
- `shared/prompts/`: Default prompt templates
