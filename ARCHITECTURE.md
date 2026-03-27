# AGI System Architecture

## Design Principles

1. **Modularity** - Testable components
2. **Extensibility** - Plugin skill system
3. **Observability** - Traceable decisions
4. **Safety** - Human review for self-modification

## Architecture

```
┌─────────────┐
│   Agent     │ ← Cognitive loop
│  Core       │   perceive/reason/act/reflect
└──────┬──────┘
       │
┌──────┴──────┬─────────────┬──────────────┐
│   Memory    │   Planner   │  Reflection  │
│   System    │             │   Engine     │
└─────────────┴─────────────┴──────────────┘
       │
┌──────┴────────────────────────────────────┐
│            Skills Registry                │
│   web_search | code_gen | analysis       │
└───────────────────────────────────────────┘
```

## Components

- **Agent**: Base cognitive loop
- **Memory**: Working, episodic, semantic tiers
- **Planner**: Goal decomposition
- **Reflection**: Meta-learning
- **Skills**: Extensible capabilities

## Open Decisions

1. Language: Python vs TypeScript
2. Memory store: SQLite vs vector DB
3. Planning: Rules vs LLM-based
4. Multi-agent coordination

---
*Living document*
