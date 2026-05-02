"""
Base Agent Implementation

A minimal but extensible agent architecture based on 2026 research:
- Cartesian agency: clear separation between core and interface
- Test-time adaptation: refinement during execution
- Constitutional governance: safety-first self-modification
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from core.memory import Memory, MemoryType, create_memory


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    WAITING = "waiting"


@dataclass
class AgentIdentity:
    """Persistent identity across sessions - inspired by Ouroboros"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "AGI-Agent"
    version: str = "0.1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    core_values: List[str] = field(default_factory=lambda: [
        "safety_first",
        "incremental_progress",
        "test_everything",
        "document_findings"
    ])
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "core_values": self.core_values
        }


@dataclass
class Task:
    """A task for the agent to execute"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    goal: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Any = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "goal": self.goal,
            "context": self.context,
            "parent_id": self.parent_id,
            "subtasks": self.subtasks,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class BaseAgent:
    """
    Base agent with integrated memory system.
    
    Features:
    - Identity persistence
    - State management  
    - Skill registry
    - Integrated memory (working, episodic, semantic, procedural)
    - Automatic memory consolidation
    - Memory-aware task execution
    """
    
    def __init__(self, identity: Optional[AgentIdentity] = None, 
                 memory_adapter: str = "memory",
                 memory_path: Optional[str] = None):
        self.identity = identity or AgentIdentity()
        self.state = AgentState.IDLE
        
        # Initialize memory system
        if memory_adapter == "file" and memory_path:
            self.memory = create_memory("file", storage_dir=memory_path)
        else:
            self.memory = create_memory("memory")
        
        # Store agent identity in semantic memory
        self.memorize_fact(
            content={"agent_identity": self.identity.to_dict()},
            category="identity",
            importance=1.0
        )
        
        self.skills: Dict[str, Callable] = {}
        self.current_task: Optional[Task] = None
        self.task_history: List[Task] = []
        self.reflection_enabled = True
        
    def register_skill(self, name: str, skill: Callable, 
                       store_in_memory: bool = True) -> None:
        """Register a skill function, optionally store in procedural memory."""
        self.skills[name] = skill
        
        if store_in_memory:
            self.learn_skill(
                skill_name=name,
                skill_description=getattr(skill, '__doc__', 'No description'),
                importance=0.8
            )
    
    def remember(self, content: Any, context: Optional[Dict] = None,
                 importance: float = 0.5) -> str:
        """
        Store experience in working memory.
        Auto-consolidates to episodic when working memory is full (Miller's Law).
        
        Args:
            content: The experience/content to remember
            context: Additional context metadata
            importance: Importance score (0.0-1.0)
        
        Returns:
            Memory ID
        """
        metadata = context or {}
        metadata['agent_state'] = self.state.value
        metadata['timestamp'] = datetime.now().isoformat()
        
        return self.memory.store(
            content=content,
            memory_type=MemoryType.WORKING,
            metadata=metadata,
            importance=importance
        )
    
    def recall(self, query: Optional[str] = None, 
               memory_type: Optional[MemoryType] = None,
               limit: int = 5,
               min_importance: float = 0.0) -> List[Dict]:
        """
        Recall memories matching criteria.
        
        Args:
            query: Optional search query
            memory_type: Filter by memory type
            limit: Maximum results
            min_importance: Minimum importance threshold
        
        Returns:
            List of memory entries
        """
        return self.memory.recall(
            query=query,
            memory_type=memory_type,
            limit=limit,
            min_importance=min_importance
        )
    
    def memorize_fact(self, content: Any, category: str = "general",
                      importance: float = 0.5) -> str:
        """
        Store a fact in semantic (long-term) memory.
        
        Args:
            content: The fact to memorize
            category: Fact category
            importance: Importance score (0.0-1.0)
        
        Returns:
            Memory ID
        """
        return self.memory.store(
            content=content,
            memory_type=MemoryType.SEMANTIC,
            metadata={"category": category, "type": "fact"},
            importance=importance
        )
    
    def learn_skill(self, skill_name: str, 
                    skill_description: str,
                    importance: float = 0.5) -> str:
        """
        Store a skill in procedural memory.
        
        Args:
            skill_name: Name of the skill
            skill_description: Description of what the skill does
            importance: Importance score (0.0-1.0)
        
        Returns:
            Memory ID
        """
        return self.memory.store(
            content={
                "skill_name": skill_name,
                "description": skill_description,
                "registered": True
            },
            memory_type=MemoryType.PROCEDURAL,
            metadata={"type": "skill", "available": skill_name in self.skills},
            importance=importance
        )
    
    def get_memory_context(self, task_description: str, 
                          limit: int = 7) -> Dict[str, Any]:
        """
        Retrieve relevant memory context for a task.
        
        Based on research: Working memory capacity is ~7 items (Miller's Law).
        Retrieves most relevant memories across all types.
        
        Args:
            task_description: Current task for relevance matching
            limit: Maximum memories to retrieve (default 7 for Miller's Law)
        
        Returns:
            Dictionary with working, episodic, semantic, and procedural memories
        """
        # Get working memory (current context)
        working = self.memory.get_working_memory()
        
        # Get relevant episodic memories (past experiences)
        episodic = self.recall(
            query=task_description,
            memory_type=MemoryType.EPISODIC,
            limit=limit
        )
        
        # Get relevant semantic memories (facts/knowledge)
        semantic = self.recall(
            query=task_description,
            memory_type=MemoryType.SEMANTIC,
            limit=limit // 2
        )
        
        # Get procedural memories (available skills)
        procedural = self.recall(
            memory_type=MemoryType.PROCEDURAL,
            limit=limit // 2
        )
        
        return {
            "working_memory": working,
            "episodic_memories": episodic,
            "semantic_memories": semantic,
            "procedural_memories": procedural,
            "total_context_items": len(working) + len(episodic) + len(semantic) + len(procedural)
        }
    
    def get_identity(self) -> Dict:
        """Return agent identity as dict"""
        return self.identity.to_dict()
    
    def create_task(self, description: str, goal: str, 
                    context: Optional[Dict] = None,
                    parent_id: Optional[str] = None) -> Task:
        """Create a new task"""
        task = Task(
            description=description,
            goal=goal,
            context=context or {},
            parent_id=parent_id
        )
        
        # Store task creation in working memory
        self.remember(
            content={"event": "task_created", "task": task.to_dict()},
            context={"task_id": task.id, "goal": goal},
            importance=0.6
        )
        
        return task
    
    def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """Execute a registered skill with memory logging"""
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' not found. Available: {list(self.skills.keys())}")
        
        self.state = AgentState.EXECUTING
        
        # Log skill execution start
        exec_id = self.remember(
            content={"event": "skill_execution_start", "skill": skill_name, "args": kwargs},
            importance=0.4
        )
        
        try:
            result = self.skills[skill_name](**kwargs)
            
            # Log success
            self.remember(
                content={"event": "skill_execution_success", "skill": skill_name, "result_preview": str(result)[:200]},
                context={"execution_id": exec_id},
                importance=0.5
            )
            
            return result
        except Exception as e:
            # Log failure
            self.remember(
                content={"event": "skill_execution_failure", "skill": skill_name, "error": str(e)},
                context={"execution_id": exec_id},
                importance=0.7
            )
            return {"error": str(e), "skill": skill_name}
        finally:
            self.state = AgentState.IDLE
    
    def execute_task(self, task: Task, max_iterations: int = 10) -> Task:
        """
        Execute a task with memory-aware planning and test-time refinement.
        
        Stores task progress and results in episodic memory for future learning.
        """
        self.current_task = task
        task.status = "in_progress"
        
        # Get memory context for this task
        memory_context = self.get_memory_context(task.description)
        task.context['memory_context'] = memory_context
        
        # Store task start in episodic memory
        self.memory.store(
            content={"event": "task_started", "task_id": task.id, "description": task.description},
            memory_type=MemoryType.EPISODIC,
            metadata={"goal": task.goal},
            importance=0.6
        )
        
        for iteration in range(max_iterations):
            # Planning phase with memory context
            self.state = AgentState.PLANNING
            plan = self._generate_plan(task, iteration)
            
            # Store plan in working memory
            self.remember(
                content={"event": "plan_generated", "iteration": iteration, "plan": plan},
                context={"task_id": task.id},
                importance=0.5
            )
            
            # Execution phase
            self.state = AgentState.EXECUTING
            step_result = self._execute_plan_step(plan, iteration)
            
            # Store execution result
            self.remember(
                content={"event": "step_executed", "iteration": iteration, "result": step_result},
                context={"task_id": task.id},
                importance=0.5
            )
            
            # Reflection/adaptation phase (test-time refinement)
            if self.reflection_enabled:
                self.state = AgentState.REFLECTING
                reflection = self._reflect_on_step(step_result, iteration)
                
                # Store reflection in episodic memory
                self.memory.store(
                    content={"event": "reflection", "iteration": iteration, "adapt": reflection,
                             "step_result": step_result},
                    memory_type=MemoryType.EPISODIC,
                    metadata={"task_id": task.id},
                    importance=0.6
                )
                
                if reflection:
                    self._adapt_plan(task, step_result)
            
            # Check completion
            if self._is_task_complete(task, step_result):
                task.status = "completed"
                task.result = step_result
                task.completed_at = datetime.now().isoformat()
                
                # Store task completion in episodic memory
                self.memory.store(
                    content={"event": "task_completed", "task_id": task.id, 
                             "iterations": iteration + 1, "result": step_result},
                    memory_type=MemoryType.EPISODIC,
                    metadata={"goal": task.goal, "success": True},
                    importance=0.8
                )
                
                break
        else:
            task.status = "failed"
            task.result = {"error": "Max iterations reached"}
            
            # Store failure in episodic memory
            self.memory.store(
                content={"event": "task_failed", "task_id": task.id, "reason": "max_iterations"},
                memory_type=MemoryType.EPISODIC,
                metadata={"goal": task.goal, "success": False},
                importance=0.7
            )
        
        self.task_history.append(task)
        self.current_task = None
        self.state = AgentState.IDLE
        
        # Consolidate working memory after task
        self.memory.consolidate()
        
        return task
    
    def _generate_plan(self, task: Task, iteration: int) -> Dict:
        """Generate a plan for the task using memory context"""
        # Retrieve similar past task experiences
        relevant_experiences = self.recall(
            query=task.goal,
            memory_type=MemoryType.EPISODIC,
            limit=3
        )
        
        return {
            "iteration": iteration,
            "action": "execute_skill",
            "target": task.description,
            "steps": ["analyze", "execute", "verify"],
            "relevant_past_experiences": len(relevant_experiences)
        }
    
    def _execute_plan_step(self, plan: Dict, iteration: int) -> Dict:
        """Execute a single plan step"""
        return {
            "iteration": iteration,
            "status": "executed",
            "plan": plan
        }
    
    def _reflect_on_step(self, result: Dict, iteration: int) -> bool:
        """
        Reflect on execution and decide if adaptation is needed.
        Returns True if adaptation should occur.
        """
        # Basic implementation - will be enhanced with core/reflection.py
        if "error" in result:
            return True  # Adapt on error
        return False
    
    def _adapt_plan(self, task: Task, result: Dict) -> None:
        """Adapt plan based on reflection"""
        pass  # To be implemented with core/planner.py
    
    def _is_task_complete(self, task: Task, result: Dict) -> bool:
        """Check if task is complete"""
        return result.get("status") == "success"
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return self.memory.stats()
    
    def save_agent_state(self, path: str) -> None:
        """Save complete agent state including memory"""
        state = {
            "identity": self.identity.to_dict(),
            "memory_stats": self.memory.stats(),
            "task_history_count": len(self.task_history),
            "skills_registered": list(self.skills.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def __repr__(self) -> str:
        return f"BaseAgent({self.identity.name}, {self.identity.id[:8]}, state={self.state.value})"


def example_skill(name: str = "world") -> str:
    """Example skill for testing"""
    return f"Hello, {name}!"


if __name__ == "__main__":
    # Basic test
    agent = BaseAgent()
    agent.register_skill("greet", example_skill)
    
    print("Agent Identity:", agent.get_identity())
    
    task = agent.create_task(
        description="Test greeting",
        goal="Execute a greeting skill"
    )
    
    result = agent.execute_task(task, max_iterations=1)
    print("Task Result:", result.to_dict())
    print("Agent Status:", agent.get_status())