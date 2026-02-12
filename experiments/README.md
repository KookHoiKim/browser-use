# Experiments Directory

This directory contains various experimental configurations for testing different multi-agent setups, prompts, and model combinations.

## Structure

Each experiment is self-contained in its own directory with:
- `config.yaml`: Experiment-specific configuration
- `run.sh` or `run_benchmark.sh`: Executable script to run the experiment
- `prompts/` (optional): Custom prompts that override shared prompts

## Available Experiments

### 1. `baseline_qwen3vl/`
**Purpose**: Establish baseline performance with standard multi-agent configuration

**Configuration**:
- Model: Qwen3VL_32b via vLLM
- Agents: Planner + Searcher + Critic (all enabled)
- Prompts: Default from `shared/prompts/`

**Run**:
```bash
cd baseline_qwen3vl
./run.sh "Your task here"

# With environment variables
HEADLESS=true ./run.sh "Your task"
MAX_STEPS=30 ./run.sh "Your task"
```

### 2. `no_critic_experiment/`
**Purpose**: Test performance without critic to measure its impact

**Configuration**:
- Model: Qwen3VL_32b via vLLM
- Agents: Planner + Searcher only (Critic DISABLED)
- Prompts: Default from `shared/prompts/`

**Hypothesis**: Removing critic may speed up execution but reduce accuracy

**Run**:
```bash
cd no_critic_experiment
./run.sh "Your task here"
```

### 3. `custom_prompts_v1/`
**Purpose**: Test improved planner prompt with enhanced decision strategy

**Configuration**:
- Model: Qwen3VL_32b via vLLM
- Agents: Planner + Searcher + Critic (all enabled)
- Prompts: **Custom planner** in `prompts/planner.md`, others default

**Changes**: Enhanced planner prompt with more detailed guidelines

**Run**:
```bash
cd custom_prompts_v1
./run.sh "Your task here"
```

### 4. `mind2web_baseline/`
**Purpose**: Benchmark multi-agent system on Mind2Web dataset

**Configuration**:
- Model: Qwen3VL_32b via vLLM
- Agents: Planner + Searcher + Critic (all enabled)
- Dataset: osunlp/Online-Mind2Web (HuggingFace)

**Prerequisites**:
1. Accept dataset terms at https://huggingface.co/datasets/osunlp/Online-Mind2Web
2. Set `HF_TOKEN` environment variable

**Run**:
```bash
cd mind2web_baseline

# Run full benchmark
./run_benchmark.sh

# Run with custom settings
CONCURRENCY=5 ./run_benchmark.sh

# Test with limited tasks
MAX_TASKS=10 ./run_benchmark.sh
```

## Creating a New Experiment

1. **Copy an existing experiment** as a template:
   ```bash
   cp -r baseline_qwen3vl my_new_experiment
   cd my_new_experiment
   ```

2. **Edit `config.yaml`**:
   - Update `experiment_name`
   - Modify agent settings (enable/disable, change models, etc.)
   - Update prompt paths if using custom prompts
   - Adjust orchestrator parameters

3. **Edit `run.sh`** header comments:
   - Update experiment name and purpose
   - Document what's different from baseline
   - Add any specific usage instructions

4. **Add custom prompts** (optional):
   ```bash
   mkdir prompts
   # Copy and modify prompts you want to customize
   cp ../../shared/prompts/planner.md prompts/
   # Edit prompts/planner.md
   ```

5. **Update config to use custom prompts**:
   ```yaml
   agents:
     planner:
       prompt_path: experiments/my_new_experiment/prompts/planner.md
   ```

6. **Test your experiment**:
   ```bash
   ./run.sh "Test task"
   ```

## Comparing Experiments

To compare results from different experiments:

1. **Check results directory**:
   ```bash
   ls -la ../../results/
   ```

2. **Review experiment logs**:
   ```bash
   # Each experiment creates a timestamped subdirectory
   cat ../../results/baseline_qwen3vl_TIMESTAMP/run.log
   cat ../../results/no_critic_experiment_TIMESTAMP/run.log
   ```

3. **Compare configurations side-by-side**:
   ```bash
   diff baseline_qwen3vl/config.yaml no_critic_experiment/config.yaml
   ```

## Environment Variables

All experiments support these environment variables:

- `HEADLESS=true/false`: Run browser in headless mode (default: false)
- `MAX_STEPS=N`: Override max steps from config
- `LOG_LEVEL=DEBUG/INFO/WARNING/ERROR`: Set logging verbosity
- `HF_TOKEN=xxx`: HuggingFace token (for Mind2Web benchmark)

## Results Storage

Results are automatically saved to:
```
results/
├── <experiment_name>_<timestamp>/
│   ├── run.log
│   ├── screenshots/
│   ├── dom_snapshots/
│   └── ...
```

## Tips

1. **Start with baseline**: Run `baseline_qwen3vl` first to establish performance metrics
2. **Change one thing**: When creating experiments, change one variable at a time
3. **Document changes**: Always update the header comments in `run.sh` and `config.yaml`
4. **Use meaningful names**: Name experiments after what they test (e.g., `high_temperature_test`)
5. **Track results**: Keep a spreadsheet or notes comparing success rates across experiments
