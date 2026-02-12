# MOVED: prompts/

⚠️ **This directory has been moved.**

Prompts have been moved to `shared/prompts/` as part of the new experiment structure.

## New Location

```
shared/prompts/
├── planner.md
├── searcher.md
└── critic.md
```

## Usage

### In experiment configs:
```yaml
agents:
  planner:
    prompt_path: shared/prompts/planner.md  # Use shared prompts
```

### For custom prompts:
```bash
# Create experiment-specific prompts
mkdir experiments/my_experiment/prompts
cp shared/prompts/planner.md experiments/my_experiment/prompts/

# Reference in config
prompt_path: experiments/my_experiment/prompts/planner.md
```

## See Also

- `EXPERIMENTS.md`: Complete guide to new structure
- `experiments/README.md`: How to use experiments
- `shared/prompts/`: New location of default prompts
