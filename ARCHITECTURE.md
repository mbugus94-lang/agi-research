# AGI Agent Architecture

## Overview

The agi-research project implements a modular, extensible architecture for autonomous AI agents with the following key principles:

1. **Separation of Concerns**: Memory, planning, reflection, and tool execution are independent modules
2. **Unified Tool Interface**: All capabilities expose consistent schemas via the Tool Registry
3. **Observability**: Full execution history, metrics, and state inspection
4. **Safety**: Risk-level classification, human-in-the-loop for self-modifications

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Integrated Agent                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Memory  │  │ Planner  │  │Reflection│  │  Tools   │        │
│  │  System  │  │          │  │          │  │ Registry │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴──────┬──────┴─────────────┘               │
│                            ▼                                   │
│                    ┌───────────────┐                           │
│                    │  ReAct Loop   │                           │
│                    │  (Reason+Act) │                           │
│                    └───────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Tool Registry (skills/tool_registry.py)

Central registry for all agent capabilities:

- **Schema Definition**: Tools declare parameters, types, descriptions (OpenAI/Anthropic compatible)
- **Risk Classification**: SAFE, NORMAL, ELEVATED, CRITICAL levels for governance
- **Auto-discovery**: Register functions via introspection or class-based tools
- **Execution History**: Full audit trail of tool calls

```python
# Built-in tools:
- web_search: Search the web with time-range filtering
- file_read: Read files with offset/limit
- file_write: Write files with backup option
- calculator: Safe mathematical evaluation
- file_list: Directory listing with patterns
- file_search: Content search within files
```

### 2. Integrated Agent (core/integrated_agent.py)

Combines all subsystems into a unified execution environment:

```python
agent = IntegratedAgent(AgentConfig(
    name="MyAgent",
    max_steps=10,
    enable_planning=True,
    enable_reflection=True
))

result = agent.run("Research AI trends and write a summary")
```

Features:
- Automatic task decomposition via Planner
- Context-aware tool selection
- Memory-enhanced reasoning
- Performance tracking and reflection
- Full state introspection via `get_state()`

### 3. Memory System (core/memory.py)

Three-tier memory architecture:

- **Working Memory**: Short-term context (FIFO, limited capacity)
- **Episodic Memory**: Task history with outcomes (persistent)
- **Semantic Memory**: Key-value facts and knowledge

```python
memory.add_to_context("User asked about Python")  # Working
memory.record_episode(task, outcome, lessons)      # Episodic
memory.learn_fact("python_created", "1991")        # Semantic
```

### 4. Task Planner (core/planner.py)

Hierarchical task decomposition:

- Rule-based goal decomposition (expandable to LLM-based)
- Dependency tracking between subtasks
- Execution order resolution
- Progress tracking with status updates

### 5. Reflection System (core/reflection.py)

Self-improvement through metacognition:

- Performance metrics tracking (steps, time, errors)
- Pattern analysis over multiple runs
- Improvement suggestions based on trends
- Self-modification proposals (human-reviewed)

```python
# Proposes changes, never auto-applies
improver.propose_change(
    component="agent",
    change_description="Add retry logic",
    rationale="API timeouts observed",
    expected_impact="Reduce failure rate"
)
```

### 6. Base Agent (core/agent.py)

ReAct pattern implementation:

```
THOUGHT → ACTION → OBSERVATION → (repeat)
```

- Pure reasoning loop without external dependencies
- Extensible for LLM-based reasoning
- Tool execution via registry

## Skill System

Skills extend `BaseTool` and define:

```python
class MySkill(BaseTool):
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="my_skill",
            description="What this skill does",
            parameters=[
                ToolParameter(name="input", type="string", description="...", required=True)
            ],
            category=ToolCategory.WEB,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(self, input: str) -> Any:
        # Implementation
        return result
```

## Tool Categories

| Category | Risk Level | Examples |
|----------|-----------|----------|
| WEB | SAFE | Search, fetch |
| FILE | ELEVATED | Read, write, delete |
| CODE | ELEVATED | Execute, generate |
| DATA | SAFE | Query, analyze |
| SYSTEM | CRITICAL | Shell, network |
| EXTERNAL_API | NORMAL | Third-party APIs |

## Testing

All components have integration tests:

```bash
python experiments/test_agent.py
```

Tests cover:
- Tool Registry (schema, execution, stats)
- Memory System (all three tiers)
- Task Planner (decomposition, execution)
- Reflection (metrics, suggestions)
- Integrated Agent (full stack)
- Skills (web search, file ops)

## Future Extensions

- **LLM Integration**: Replace rule-based reasoning with actual LLM calls
- **Vector Memory**: Semantic search with embeddings
- **Multi-Agent Orchestration**: Agent-to-agent communication
- **Durable Execution**: Persist state for long-running tasks
- **Streaming**: Real-time output for interactive use
- **Human-in-the-Loop**: Approval gates for critical operations
