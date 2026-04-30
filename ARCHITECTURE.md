# AGI Research Architecture

System design documentation for the AGI Research & Build project.

---

## 🏛️ Architectural Principles

Based on 2026 research findings, this system follows:

1. **Modularity**: Components are independently testable and replaceable
2. **Memory-Centric**: Memory systems are foundational (SMGI theory [^7])
3. **Adaptive**: Test-time adaptation and refinement (ARC-AGI findings [^11])
4. **Observable**: Built-in tracing and evaluation (VoltAgent pattern [^13])
5. **Safe**: Sandboxed execution, review gates for self-modification

---

## 📊 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      AGI System                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Agent      │  │   Planner    │  │  Reflection  │      │
│  │   (core)     │◄─┤   (core)     │◄─┤   (core)     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │              │
│         └────────────┬────┴─────────────────┘              │
│                      │                                      │
│              ┌───────▼───────┐                             │
│              │    Memory     │                             │
│              │   (core)      │                             │
│              └───────┬───────┘                             │
│                      │                                      │
│         ┌────────────┼────────────┐                        │
│         ▼            ▼            ▼                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │ Working  │ │ Long-term│ │ Semantic │                   │
│  │ Memory   │ │ Memory   │ │ Memory   │                   │
│  └──────────┘ └──────────┘ └──────────┘                   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                         Skills                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Web      │ │ Code     │ │ Analysis │ │  Tool    │        │
│  │ Search   │ │ Generate │ │   &      │ │  Use     │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Core Components

### 1. Memory System (`core/memory.py`)

**Purpose**: Unified interface for all memory operations.

**Design Inspired By**:
- SMGI: Learning interface evolves [^7]
- LLM-in-Sandbox: Filesystem-backed long context [^9]
- ARC-AGI: Test-time adaptation requires memory [^11]

**Memory Types**:
```python
class MemoryType(Enum):
    WORKING = "working"      # Short-term, limited capacity
    EPISODIC = "episodic"    # Event sequences
    SEMANTIC = "semantic"    # Facts and knowledge
    PROCEDURAL = "procedural" # Skills and procedures
```

**Interface**:
```python
class Memory:
    def store(self, content, memory_type, metadata=None)
    def retrieve(self, query, memory_type=None, limit=10)
    def update(self, memory_id, new_content)
    def forget(self, memory_id)
    def consolidate(self)  # Working -> Long-term
```

**Adapters**:
- `InMemoryAdapter`: Fast, non-persistent
- `FileAdapter`: Persistent, JSON-backed
- `VectorAdapter`: Semantic search (future)

### 2. Agent Base (`core/agent.py`)

**Purpose**: Core agent loop with perception-action cycle.

**Design Inspired By**:
- OpenAI Agents SDK: Tool use, guardrails [^12]
- Microsoft Agent Framework: Graph-based state [^14]

**Key Features**:
- Perception: Input processing from environment
- Memory: Access to working and long-term memory
- Planning: Goal decomposition via planner
- Action: Tool execution with safety checks
- Reflection: Post-action evaluation

```python
class Agent:
    def __init__(self, memory, planner, skills, config)
    def perceive(self, observation)
    def think(self, goal)
    def act(self, action_plan)
    def reflect(self, action_result)
    def run(self, task, max_iterations=10)
```

### 3. Planner (`core/planner.py`)

**Purpose**: Task decomposition and strategy selection.

**Design Inspired By**:
- ARC-AGI: Compositional reasoning critical [^11]
- Geometry of Benchmarks: GVU operator [^8]

**Capabilities**:
- Hierarchical task decomposition
- Strategy selection based on task type
- Sub-goal management
- Plan revision on failure

```python
class Planner:
    def decompose(self, task) -> List[SubTask]
    def select_strategy(self, task) -> Strategy
    def create_plan(self, task, context) -> Plan
    def revise_plan(self, plan, failure_reason) -> Plan
```

### 4. Reflection (`core/reflection.py`)

**Purpose**: Self-evaluation and improvement.

**Design Inspired By**:
- Appier AI Self-Awareness: Risk detection [^1]
- SMGI: Evaluative invariance [^7]

**Functions**:
- Action outcome evaluation
- Strategy effectiveness assessment
- Self-improvement proposal (requires review)
- Error pattern recognition

```python
class Reflection:
    def evaluate_action(self, action, result, expected)
    def assess_strategy(self, strategy, outcomes)
    def propose_improvement(self) -> Proposal
    def recognize_patterns(self, history) -> Patterns
```

---

## 🛠️ Skills System

Skills are capability modules that agents can invoke.

### Skill Interface:
```python
class Skill:
    name: str
    description: str
    parameters: Dict[str, Type]
    
    def execute(self, **kwargs) -> Result
    def validate(self, **kwargs) -> bool
```

### Planned Skills:
1. **WebSearch**: Search and retrieve web content
2. **CodeGenerate**: Write and execute code
3. **Analysis**: Data analysis and pattern recognition
4. **ToolUse**: Generic tool invocation (MCP compatible)

---

## 🧪 Experiment Framework

All components must be validated through experiments.

### Experiment Structure:
```
experiments/
├── test_memory.py       # Memory system validation
├── test_agent.py        # Agent loop validation
├── test_planner.py      # Planning validation
└── benchmarks/          # ARC-AGI style tests
```

### Test Categories:
1. **Unit Tests**: Component isolation
2. **Integration Tests**: Component interaction
3. **Stress Tests**: Performance under load
4. **Benchmarks**: Comparison to baselines

---

## 🔒 Safety Architecture

Following research on trustworthy AI [^1]:

### Guardrails:
1. **Action Validation**: All actions validated before execution
2. **Sandbox**: Code execution in isolated environment
3. **Review Gates**: Self-modifications require human review
4. **Logging**: Complete trace of all decisions

### Self-Improvement Protocol:
```
Agent proposes change → Store in proposals/ → Human review → Apply/Reject
```

---

## 📈 Evolution Strategy

The system evolves based on:

1. **Research Integration**: New papers inform design
2. **Benchmark Results**: ARC-AGI style tests guide improvement
3. **Component Refinement**: Each iteration improves one component
4. **Emergent Behavior**: Multi-agent interaction experiments

---

## 🔄 Data Flow

```
Input → Perceive → Memory.retrieve → Plan → Act → Reflect → Memory.store
                    ↑                                      ↓
                    └────────────── Feedback ←─────────────┘
```

---

## 📝 Implementation Notes

### Technology Stack:
- Python 3.10+
- Type hints throughout
- Async support for I/O operations
- JSON for persistence
- pytest for testing

### Design Patterns:
- Adapter pattern for memory backends
- Strategy pattern for planning
- Observer pattern for reflection
- Plugin architecture for skills

---

## 🎯 Success Metrics

1. **Memory**: Retrieval accuracy > 90%
2. **Planning**: Task completion rate > 80%
3. **Reflection**: Error detection rate > 75%
4. **Integration**: End-to-end task success > 70%

---

**Version**: 0.1.0  
**Last Updated**: 2026-04-30
