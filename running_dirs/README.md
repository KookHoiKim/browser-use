# DEPRECATED: running_dirs/

⚠️ **This directory structure is deprecated.**

The project has moved to a new experiment-centric structure for better organization and reproducibility.

## Migration Guide

### Old Structure (Deprecated)
```
running_dirs/
├── run_multiagent.py
├── run_mind2web.py
└── run.sh
```

### New Structure (Use This)
```
browser-use/
├── runners/              # Generic runner scripts
├── experiments/          # Self-contained experiments
│   ├── baseline_qwen3vl/
│   │   ├── config.yaml
│   │   ├── run.sh
│   │   └── prompts/ (optional)
│   └── ...
├── shared/              # Shared resources
│   ├── prompts/
│   └── configs/
└── results/             # Auto-generated results
```

## How to Migrate

### If you were using `run_multiagent.py`:
```bash
# Old way:
python running_dirs/run_multiagent.py --config configs/multiagent_default.yaml --task "..."

# New way:
cd experiments/baseline_qwen3vl
./run.sh "Your task here"
```

### If you were using `run_mind2web.py`:
```bash
# Old way:
python running_dirs/run_mind2web.py --config configs/mind2web_benchmark.yaml

# New way:
cd experiments/mind2web_baseline
./run_benchmark.sh
```

### If you had custom configurations:
```bash
# Create new experiment folder
mkdir experiments/my_experiment
cp experiments/baseline_qwen3vl/run.sh experiments/my_experiment/

# Copy your old config
cp configs/my_config.yaml experiments/my_experiment/config.yaml

# Update config to use new structure
# - Change prompt_path to shared/prompts/... or experiments/my_experiment/prompts/...
# - Change run_dir_base to results

# Run it
cd experiments/my_experiment
./run.sh "Your task"
```

## Why This Change?

The new structure provides:

1. **Better Reproducibility**: Each experiment is self-contained with its config and run script
2. **Clear Documentation**: `run.sh` shows exactly what settings were used
3. **Easy Comparison**: Compare experiments by comparing their folders
4. **Version Control**: Git tracks experiment configurations over time
5. **Less Confusion**: No need to remember complex command-line arguments

## Documentation

See these files for complete information:

- **`EXPERIMENTS.md`**: Complete guide to the new structure
- **`experiments/README.md`**: Detailed experiment documentation
- **`shared/prompts/`**: Default prompt templates
- **`shared/configs/`**: Base configuration templates

## Timeline

- **Before 2026-02-12**: Old `running_dirs/` structure
- **2026-02-12**: New `experiments/` structure introduced
- **Future**: `running_dirs/` will be removed entirely

Please migrate your workflows to the new structure.

## Need Help?

1. Read `EXPERIMENTS.md` in project root
2. Look at example experiments in `experiments/`
3. Copy an existing experiment as a template

## Original Files

The original runner scripts are preserved in `runners/` directory:
- `runners/multiagent_runner.py` (was `run_multiagent.py`)
- `runners/mind2web_runner.py` (was `run_mind2web.py`)

These are now generic runners called by experiment `run.sh` scripts.
