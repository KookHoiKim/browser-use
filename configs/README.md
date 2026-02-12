# MOVED: configs/

⚠️ **This directory has been moved.**

Configs have been moved to `shared/configs/` as part of the new experiment structure.

## New Location

```
shared/configs/
├── multiagent_default.yaml
├── multiagent_azure.yaml
└── mind2web_benchmark.yaml
```

## Usage

### Don't use shared configs directly!

Instead, create experiment-specific configs:

```bash
# Create new experiment
mkdir experiments/my_experiment

# Create config (copy from template or customize)
cp shared/configs/multiagent_default.yaml experiments/my_experiment/config.yaml

# Edit config
vim experiments/my_experiment/config.yaml

# Run experiment
cd experiments/my_experiment
./run.sh "Your task"
```

## Why Not Use Shared Configs?

The new structure is **experiment-centric**:
- Each experiment has its own `config.yaml`
- This makes experiments self-contained and reproducible
- You can see exactly what settings were used by looking at the experiment folder

## Template Configs

Use `shared/configs/` as **templates** to copy from, not as configs to reference directly.

## See Also

- `EXPERIMENTS.md`: Complete guide to new structure
- `experiments/README.md`: How to create experiments
- `shared/configs/`: Template configs to copy from
