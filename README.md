# AGI Research & Build

Continuous research and incremental building toward Artificial General Intelligence.

## 🎯 Mission

This repository documents ongoing research into AGI and implements core components incrementally. The approach follows these principles:

- **Incremental progress**: Working code over perfect architecture
- **Test everything**: All components must be validated
- **Research-driven**: Implementation informed by latest findings
- **Safety first**: Self-modifications require review
- **Daily compounding**: Small, consistent progress

## 📁 Repository Structure

```
agi-research/
├── README.md                 # This file
├── CURRENT_RESEARCH.md       # Latest research findings
├── ARCHITECTURE.md          # System design documentation
├── core/                    # Core AGI components
│   ├── agent.py            # Base agent implementation
│   ├── memory.py           # Memory systems
│   ├── planner.py          # Planning and reasoning
│   └── reflection.py       # Self-reflection capabilities
├── skills/                 # Capability modules
│   └── [TBD]
└── experiments/            # Validation tests
    └── [TBD]
```

## 🔄 Continuous Workflow

This project runs on a scheduled agent that executes:

1. **Research Phase** (~15 min)
   - Search for latest AGI research
   - Review arXiv papers
   - Identify trending frameworks
   - Document findings

2. **Repo Maintenance**
   - Ensure structure exists
   - Update documentation
   - Review previous changes

3. **Build Phase**
   - Implement one component
   - Add one skill
   - Create one experiment
   - OR refactor existing code

4. **Git Workflow**
   - Pull latest changes
   - Commit with timestamp
   - Push to origin

## 🏗️ Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Memory | 🔄 In Progress | Base interface + adapters |
| Agent Base | ⏳ Planned | Core agent loop |
| Planner | ⏳ Planned | Task decomposition |
| Reflection | ⏳ Planned | Self-improvement |
| Skills | ⏳ Planned | Capability modules |
| Experiments | ⏳ Planned | Validation suite |

## 📚 Research Sources

- arXiv CS.AI, CS.CL, CS.LG
- Open-source GitHub repositories
- AI research newsletters
- Conference proceedings (NeurIPS, ICML, ICLR)

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/dave92/agi-research.git
cd agi-research

# Install dependencies
pip install -r requirements.txt

# Run experiments
python -m experiments.test_memory
```

## 📝 Contributing

This is a research project. All changes are:
1. Research-informed
2. Incrementally tested
3. Documented in CURRENT_RESEARCH.md
4. Committed with descriptive messages

## 📖 Key Research Insights

See `CURRENT_RESEARCH.md` for detailed findings including:
- Latest AGI breakthroughs
- AI agent architecture trends 2026
- Recent arXiv papers
- Trending open-source frameworks

## 🔮 Future Directions

Based on current research:
- SMGI-inspired structural learning
- GVU (Generator-Verifier-Updater) loops
- ARC-AGI reasoning benchmarks
- Multi-agent orchestration

---

**Last Updated:** 2026-04-30
