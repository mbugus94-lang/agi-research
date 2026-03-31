# AGI Research & Build Project

A continuous research and implementation effort toward AGI-capable AI agents.

## Philosophy
- Incremental, working code over perfect architecture
- Test everything
- Document findings continuously
- Safety: All self-modifications require REVIEW
- Small, daily progress compounds

## Structure
```
agi-research/
├── README.md              # This file
├── CURRENT_RESEARCH.md    # Weekly research findings
├── ARCHITECTURE.md        # System design docs
├── core/                  # Core agent components
│   ├── agent.py          # Base agent class
│   ├── memory.py         # Memory management
│   ├── planner.py        # Task planning
│   └── reflection.py     # Self-improvement
├── skills/               # Capability modules
│   └── [tool modules]
└── experiments/          # Validation tests
    └── test_*.py
```

## Quick Start
```bash
cd /home/workspace/agi-research
python -m experiments.test_agent
```

## Research Focus Areas
1. Multi-agent orchestration patterns
2. Memory systems (episodic, semantic, procedural)
3. Tool use and skill acquisition
4. Self-reflection and improvement
5. Reasoning and planning architectures

## Current Status
See `CURRENT_RESEARCH.md` for latest findings and active work items.
