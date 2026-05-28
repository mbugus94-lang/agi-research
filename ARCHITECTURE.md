# AGI System Architecture

## Core Philosophy

Based on current research (May 2026), the architecture follows:
- **System-1**: LLM as pattern repository (fast, intuitive)
- **System-2**: Coordination layer (slow, deliberate, verifiable)

## System Components

### Core Layer

```
┌─────────────────────────────────────────────────────────┐
│                    COORDINATION LAYER                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   Planner   │  │  Reflector  │  │  Memory Manager │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    AGENT RUNTIME                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Base Agent  │  │ Sub-agents  │  │   Tool Registry  │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    LLM INTERFACE                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   OpenAI    │  │  Anthropic  │  │    Local/Other   │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Design Decisions

1. **Agent Loop**: EXPLORE → VERIFY → PLAN → EXECUTE → REFLECT
2. **Memory**: Hierarchical (working, episodic, semantic)
3. **Tools**: MCP protocol for extensibility
4. **Safety**: Reactive self-correction, human-in-the-loop for critical actions

### Key Patterns

- **UCCT (Unified Contextual Control Theory)**: Semantic anchoring
- **RCA (Recursive Causal Audit)**: Trace-answer verification
- **MACI**: Multi-agent coordination with diversity and filtering

## Skills Architecture

Each skill is a self-contained module with:
- Input/output schema
- Tool dependencies
- Required permissions
- Fallback behavior

## Experiments Structure

```
experiments/
├── hypothesis_001_explore_before_plan/
├── hypothesis_002_coordination_layer_impact/
└── hypothesis_003_self_correction_security/
```

Each experiment includes:
- `hypothesis.md`: What we're testing
- `setup.py`: Experiment code
- `results/`: Output data
- `conclusion.md`: Findings and implications
