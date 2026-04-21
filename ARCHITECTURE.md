# AGI Architecture

## Core Philosophy

Based on 2026 research insights, this architecture emphasizes:

1. **Cartesian Agency**: Clear separation between learned core and explicit runtime interface
2. **Test-Time Adaptation**: Refinement loops for continuous improvement
3. **Compositional Reasoning**: Building complex behaviors from simple primitives
4. **Constitutional Governance**: Safety constraints before self-modification

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENT RUNTIME                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Agent     │  │   Memory    │  │      Planner        │   │
│  │   Core      │◄─┤   System    │◄─┤  (with Refinement)  │   │
│  │             │  │             │  │                     │   │
│  │ - Identity  │  │ - Working   │  │ - Decomposition     │   │
│  │ - Reasoning │  │ - Episodic  │  │ - Reflection        │   │
│  │ - Values    │  │ - Semantic  │  │ - Test-Time Adapt   │   │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘   │
│         │                                                    │
│         ▼                                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              SYMBOLIC INTERFACE LAYER                   │  │
│  │    (Governed by Constitution - BIBLE.md equivalent)    │  │
│  └────────────────────────────────────────────────────────┘  │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Skills    │  │   Tools     │  │    Multi-Agent      │   │
│  │   Registry  │  │   (MCP)     │  │      Review         │   │
│  │             │  │             │  │                     │   │
│  │ - WebSearch │  │ - File Ops  │  │ - Code Review       │   │
│  │ - CodeGen   │  │ - Shell     │  │ - Safety Check      │   │
│  │ - Analysis  │  │ - Browser   │  │ - Consensus         │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Agent Core (`core/agent.py`)
- **Identity**: Persistent self-model across sessions
- **Reasoning**: Chain-of-thought with reflection integration
- **Values**: Constitutional constraints from governance layer

### Memory System (`core/memory.py`)
- **Working Memory**: Current context and active goals
- **Episodic Memory**: Past experiences with outcomes
- **Semantic Memory**: Learned facts and patterns
- **Procedural Memory**: Skill execution traces

### Planner (`core/planner.py`)
- **Task Decomposition**: Break complex goals into subtasks
- **Reflection Integration**: Learn from past planning failures
- **Test-Time Refinement**: Adapt plan during execution based on feedback
- **Compositional Assembly**: Build plans from reusable components

### Reflection System (`core/reflection.py`)
- **Self-Evaluation**: Assess own performance
- **Error Analysis**: Identify failure modes
- **Improvement Proposals**: Suggest architectural changes
- **Safety Review**: Flag risky modifications

### Governance Layer
- **Constitution**: BIBLE.md equivalent with core principles
- **Multi-Model Review**: Multiple LLMs review changes before commit
- **Human-in-the-Loop**: Critical changes require approval

## Research-Driven Design Decisions

1. **From ARC-AGI**: Test-time adaptation loops are critical
2. **From Cartesian Agency**: Explicit symbolic interface for safety
3. **From Self-Evolving Agents**: Curriculum learning for skill acquisition
4. **From Multi-Agent Research**: Internal deliberation improves outcomes

## Evolution Roadmap

1. **Phase 1**: Basic agent with memory and planning
2. **Phase 2**: Add test-time refinement loops
3. **Phase 3**: Implement compositional reasoning
4. **Phase 4**: Add self-reflection and improvement proposals
5. **Phase 5**: Enable governed self-modification with review
