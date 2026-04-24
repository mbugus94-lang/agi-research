# AGI Agent Architecture

## System Overview

This project implements a modular, self-evolving agent architecture inspired by current research (2026) on hierarchical agent systems, Model Context Protocol (MCP), and multi-agent orchestration.

## Core Components

### 1. Agent (`core/agent.py`)

The base agent class provides:
- **Identity & Role**: Configurable persona and capabilities
- **LLM Integration**: Provider-agnostic (OpenAI, Anthropic, local)
- **Tool Registry**: Dynamic tool loading and execution
- **Event Loop**: Main execution cycle for perception → reasoning → action

```
Agent
├── identity: AgentIdentity
├── llm: LLMProvider
├── tools: ToolRegistry
├── memory: MemorySystem
├── planner: Planner
├── reflection: ReflectionEngine
└── run_cycle() → Action
```

### 2. Memory System (`core/memory.py`)

Multi-tier memory architecture:

| Tier | Type | Purpose | Persistence |
|------|------|---------|-------------|
| Working | Short-term | Active context, conversation | Session |
| Episodic | Medium-term | Task history, experiences | Persistent |
| Semantic | Long-term | Knowledge, facts, skills | Persistent |
| Procedural | Learned | Tool usage patterns, heuristics | Persistent |

**Key Features**:
- Vector-based semantic search
- Importance-based retention
- Memory consolidation (working → episodic → semantic)
- Context window optimization

### 3. Planner (`core/planner.py`)

Goal decomposition and task management:

- **Hierarchical Planning**: Breaks goals into sub-goals and atomic tasks
- **Dependency Graph**: Tracks task prerequisites and ordering
- **Dynamic Replanning**: Adapts when tasks fail or context changes
- **Estimation**: Predicts time/resource needs

```
Goal
├── Task 1 (atomic or compound)
│   ├── Sub-task 1.1
│   └── Sub-task 1.2
├── Task 2
└── Task 3
```

### 4. Reflection Engine (`core/reflection.py`)

Self-improvement and learning:

- **Outcome Analysis**: Evaluates task success/failure
- **Pattern Recognition**: Identifies recurring strategies
- **Skill Assessment**: Tracks capability gaps
- **Improvement Proposals**: Suggests new tools or refinements

**Safety Note**: Reflection generates proposals but requires human review for implementation.

## Agent Types

### Single Agent
Standard autonomous agent with full capability stack.

### Supervisor Agent
Coordinates sub-agents, manages delegation:
- Task distribution
- Result aggregation
- Conflict resolution

### Sub-Agent
Specialized agent with constrained capabilities:
- Narrow tool set
- Specific domain knowledge
- Reports to supervisor

## Tool System

### Native Tools
Built-in capabilities:
- `search_web`: Internet search
- `read_file`: File system access
- `execute_code`: Sandbox code execution
- `llm_call`: Delegate to LLM

### MCP Tools
External tools via Model Context Protocol:
- Tool discovery from MCP servers
- Dynamic registration
- Cross-agent compatibility

### Dynamic Tool Generation
Code-generation capability:
- Synthesizes new tools when needed
- Tests generated tools before registration
- Maintains tool library with versioning

## Execution Flow

```
┌─────────────┐
│  Perceive   │ ← Environment, user input, tool results
└──────┬──────┘
       ↓
┌─────────────┐
│   Memory    │ ← Retrieve relevant context
│   Query     │
└──────┬──────┘
       ↓
┌─────────────┐
│   Plan      │ ← Decompose goals, select strategy
└──────┬──────┘
       ↓
┌─────────────┐
│   Reason    │ ← LLM reasoning with context
└──────┬──────┘
       ↓
┌─────────────┐
│   Act       │ ← Execute tool, delegate, respond
└──────┬──────┘
       ↓
┌─────────────┐
│   Reflect   │ ← Learn from outcome
└─────────────┘
```

## Communication Protocols

### Internal (Agent ↔ Components)
Python object messages with typed schemas.

### Inter-Agent (Agent ↔ Agent)
JSON messages with standard envelope:
```json
{
  "from": "agent_id",
  "to": "agent_id",
  "type": "delegate|report|request",
  "payload": {...},
  "timestamp": "...",
  "correlation_id": "..."
}
```

### MCP (Agent ↔ External Tools)
Model Context Protocol standard.

## State Management

### Checkpointing
- Save full agent state to disk
- Resume from any checkpoint
- Branch execution from checkpoints ("time travel")

### Persistence
- SQLite/PostgreSQL for structured data
- Vector DB for semantic memory
- File system for code artifacts

## Governance & Safety

### Built-in Controls
- **Permission System**: Tiered access (read, write, execute, network)
- **Approval Gates**: Human approval for sensitive actions
- **Rate Limiting**: Prevent runaway execution
- **Audit Logging**: Complete action history

### Kill Switches
- Soft stop: Finish current task, then halt
- Hard stop: Immediate termination
- Scope limiting: Restrict to specific domains/tools

## Configuration

```yaml
agent:
  name: "research-agent"
  model: "claude-3-5-sonnet"
  
memory:
  working_limit: 10
  vector_db: "chroma"
  
planning:
  max_depth: 5
  replan_threshold: 0.3
  
reflection:
  auto_improve: false  # Requires review
  skill_library: "./skills"
  
mcp:
  servers:
    - url: "https://mcp.example.com"
```

## Future Extensions

- [ ] Multi-agent crew coordination
- [ ] Distributed agent execution
- [ ] Continuous learning from interactions
- [ ] Natural language skill specification
- [ ] Visual workflow designer

---
*Architecture evolving with research*
