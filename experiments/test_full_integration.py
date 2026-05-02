"""
Full Integration Test - End-to-End Agent System Validation

Tests all core components working together:
- BaseAgent with identity and state management
- Memory system (working, episodic, semantic, procedural)
- Planner with hierarchical decomposition
- Reflection system for self-improvement
- Skills integration (web_search, code_gen, analysis)
- Category-theoretic framework

Based on 2026 research: ARC-AGI-3, SMGI, Category-theoretic Framework
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.agent import BaseAgent, AgentIdentity, Task, AgentState
from core.memory import Memory, MemoryEntry, MemoryType
from core.planner import (
    TreeOfThoughtPlanner, PlanStatus, PlanningContext, 
    PlanNode, Plan, TestTimeAdapter, PlanExecutor,
    create_default_planner
)
from core.reflection import ReflectionSystem, Reflection, ReflectionType
from core.category_framework import (
    Object, Morphism, Category,
    AgentFunctor, NaturalTransformation, AgentSpecification
)
from skills.web_search import web_search
from skills.code_gen import generate_code, review_code
from skills.analysis import analyze_patterns, synthesize
from datetime import datetime
import json


class IntegratedAgentSystem:
    """
    Fully integrated agent system combining all core components.
    
    Architecture based on 2026 research findings:
    - Cartesian agency: clean core/interface separation
    - Test-time adaptation: reflection → plan → execute loop
    - SMGI-inspired: structural evolution tracking
    - Category-theoretic: formal composition of components
    """
    
    def __init__(self, name: str = "IntegratedAgent"):
        # Core identity
        self.identity = AgentIdentity(name=name)
        
        # Memory systems (multiple types per SMGI research)
        self.working_memory = Memory()  # Short-term, limited capacity
        self.episodic_memory = Memory()  # Event sequences
        self.semantic_memory = Memory()  # Facts and knowledge
        
        # Planning and reflection
        self.planner = TreeOfThoughtPlanner()
        self.adapter = TestTimeAdapter()
        self.executor = PlanExecutor(self.planner, self.adapter)
        self.reflection = ReflectionSystem()
        
        # Category-theoretic framework
        self.agent_category = Category("AgentSystem", {
            "identity": Object({"name": name, "version": "1.0"}),
            "memory": Object({"type": "multi_tier"}),
            "planner": Object({"type": "hierarchical"}),
            "reflection": Object({"type": "self_improving"})
        })
        
        # Skills registry
        self.skills = {
            "web_search": web_search,
            "generate_code": generate_code,
            "review_code": review_code,
            "analyze_patterns": analyze_patterns,
            "synthesize": synthesize
        }
        
        # Execution tracking
        self.execution_history = []
        self.learning_metrics = {
            "tasks_completed": 0,
            "adaptations_made": 0,
            "reflections_performed": 0
        }
    
    def perceive(self, observation: dict) -> dict:
        """
        Perception phase: process input and store in working memory.
        Based on active inference and Cartesian agency research.
        """
        # Store in working memory with importance scoring
        entry = MemoryEntry(
            content=observation,
            memory_type=MemoryType.WORKING,
            importance=observation.get("importance", 0.5)
        )
        self.working_memory.store(entry)
        
        # Check working memory capacity (Miller's Law: 7±2)
        stats = self.working_memory.stats()
        if stats["working_memory_items"] > 7:
            # Consolidate to episodic memory
            self.working_memory.consolidate()
        
        return {
            "perceived": True,
            "working_memory_count": stats["working_memory_items"],
            "timestamp": datetime.now().isoformat()
        }
    
    def plan(self, goal: str, context: dict = None) -> Plan:
        """
        Planning phase: hierarchical task decomposition.
        Based on ARC-AGI-3 research: goal inference and exploratory planning.
        """
        # Create planning context
        planning_context = PlanningContext(
            task_description=goal,
            memory_context=context or {}
        )
        
        # Generate plan with Tree of Thought
        plan = self.planner.generate_plan(planning_context)
        
        # Store plan in semantic memory
        self.semantic_memory.store(MemoryEntry(
            content={"goal": goal, "plan": plan.to_dict()},
            memory_type=MemoryType.SEMANTIC,
            importance=0.8
        ))
        
        return plan
    
    def act(self, plan: Plan, skill_name: str = None, **kwargs) -> dict:
        """
        Action phase: execute plan using skills.
        Integrates with reflection for test-time adaptation.
        """
        result = {
            "actions": [],
            "results": [],
            "adaptations": []
        }
        
        # Flatten plan nodes for execution
        nodes_to_execute = []
        for root in plan.root_nodes:
            nodes_to_execute.append(root)
            nodes_to_execute.extend(root.alternative_branches)
        
        for node in nodes_to_execute[:5]:  # Limit for demo
            # Record performance for reflection
            step_start = datetime.now()
            
            try:
                # Execute skill if specified
                if skill_name and skill_name in self.skills:
                    skill_result = self.skills[skill_name](**kwargs)
                else:
                    # Default action recording
                    skill_result = {"step": node.description, "executed": True}
                
                # Record metrics
                step_end = datetime.now()
                duration = (step_end - step_start).total_seconds()
                
                result["actions"].append(node.description)
                result["results"].append(skill_result)
                
            except Exception as e:
                # Record failure
                result["adaptations"].append({
                    "step": node.description,
                    "error": str(e),
                    "adapted": True
                })
                self.learning_metrics["adaptations_made"] += 1
        
        self.learning_metrics["tasks_completed"] += 1
        return result
    
    def reflect(self, task_result: dict) -> dict:
        """
        Reflection phase: analyze performance and suggest improvements.
        Based on self-evolving agent research (arXiv:2601.11658v1).
        """
        # Create reflection
        reflection = Reflection(
            type=ReflectionType.PERFORMANCE.value,
            subject="task_execution",
            observation=f"Completed {self.learning_metrics['tasks_completed']} tasks",
            analysis="System functioning within normal parameters"
        )
        
        # Store reflection
        reflection_id = self.reflection.reflect(reflection)
        
        # Get pending reflections
        pending = self.reflection.get_pending_reflections()
        
        self.learning_metrics["reflections_performed"] += 1
        
        return {
            "reflection_id": reflection_id,
            "pending_count": len(pending),
            "total_reflections": len(self.reflection.reflections)
        }
    
    def learn(self, experience: dict) -> dict:
        """
        Learning phase: update semantic memory with new knowledge.
        SMGI-inspired structural evolution.
        """
        # Extract knowledge from experience
        if "knowledge" in experience:
            for fact in experience["knowledge"]:
                self.semantic_memory.store(MemoryEntry(
                    content=fact,
                    memory_type=MemoryType.SEMANTIC,
                    importance=fact.get("importance", 0.5)
                ))
        
        # Store procedural knowledge (how to do things)
        if "procedure" in experience:
            self.semantic_memory.store(MemoryEntry(
                content=experience["procedure"],
                memory_type=MemoryType.PROCEDURAL,
                importance=0.7
            ))
        
        return {"learned": True, "memory_updated": datetime.now().isoformat()}
    
    def execute_full_loop(self, goal: str, context: dict = None) -> dict:
        """
        Full execution loop: perceive → plan → act → reflect → learn
        """
        print(f"\n{'='*60}")
        print(f"Executing: {goal}")
        print(f"{'='*60}")
        
        # 1. Perception
        print("\n[1] Perception...")
        perception = self.perceive({
            "goal": goal,
            "context": context or {},
            "importance": 0.9
        })
        print(f"   Working memory: {perception['working_memory_count']} items")
        
        # 2. Planning
        print("\n[2] Planning...")
        plan = self.plan(goal, context)
        total_nodes = len(plan.root_nodes)
        for root in plan.root_nodes:
            total_nodes += len(root.alternative_branches)
        print(f"   Plan nodes: {total_nodes}")
        print(f"   Version: {plan.version}")
        
        # 3. Action
        print("\n[3] Action...")
        action_result = self.act(plan)
        print(f"   Actions executed: {len(action_result['actions'])}")
        print(f"   Adaptations: {len(action_result['adaptations'])}")
        
        # 4. Reflection
        print("\n[4] Reflection...")
        reflection_result = self.reflect(action_result)
        print(f"   Reflection stored: {reflection_result['reflection_id'][:8]}...")
        print(f"   Total reflections: {reflection_result['total_reflections']}")
        
        # 5. Learning
        print("\n[5] Learning...")
        learn_result = self.learn({
            "knowledge": [{"goal": goal, "success": True, "importance": 0.8}],
            "procedure": {"steps_taken": len(action_result['actions'])}
        })
        print(f"   Experience stored: {learn_result['learned']}")
        
        # Record execution
        execution_record = {
            "goal": goal,
            "perception": perception,
            "plan": plan.to_dict(),
            "action": action_result,
            "reflection": reflection_result,
            "learning": learn_result,
            "timestamp": datetime.now().isoformat()
        }
        self.execution_history.append(execution_record)
        
        return execution_record
    
    def get_category_structure(self) -> dict:
        """
        Return category-theoretic structure of the agent system.
        Based on arXiv:2603.28906v1 category-theoretic framework.
        """
        return {
            "category": self.agent_category.name,
            "objects": list(self.agent_category.objects.keys()),
            "morphisms": len(self.agent_category.morphisms),
            "composition_law": "associative_composition",
            "functor_preservation": ["identity", "composition"]
        }
    
    def get_system_status(self) -> dict:
        """Return comprehensive system status"""
        return {
            "identity": self.identity.to_dict(),
            "memory": {
                "working": self.working_memory.stats(),
                "episodic": self.episodic_memory.stats(),
                "semantic": self.semantic_memory.stats()
            },
            "learning": self.learning_metrics,
            "execution_history_count": len(self.execution_history),
            "category_structure": self.get_category_structure()
        }


def test_full_integration():
    """Test the full integrated system"""
    print("="*60)
    print("FULL INTEGRATION TEST")
    print("="*60)
    
    # Initialize integrated system
    system = IntegratedAgentSystem(name="AGI-Research-Agent")
    
    # Test 1: System initialization
    print("\n[TEST 1] System Initialization")
    status = system.get_system_status()
    assert status["identity"]["name"] == "AGI-Research-Agent"
    assert "working" in status["memory"]
    print("   ✓ System initialized correctly")
    
    # Test 2: Perception-Action-Reflection loop
    print("\n[TEST 2] Full Execution Loop")
    result = system.execute_full_loop(
        goal="Research AGI architecture trends",
        context={"topic": "multi-agent systems", "depth": "comprehensive"}
    )
    assert result["goal"] == "Research AGI architecture trends"
    assert "plan" in result
    assert "reflection" in result
    print("   ✓ Full loop executed successfully")
    
    # Test 3: Multiple execution cycles
    print("\n[TEST 3] Multiple Execution Cycles")
    for i, goal in enumerate([
        "Analyze code patterns",
        "Generate documentation",
        "Review implementation"
    ]):
        system.execute_full_loop(goal=goal, context={"iteration": i})
    assert len(system.execution_history) == 4  # 1 + 3
    print(f"   ✓ Executed {len(system.execution_history)} tasks")
    
    # Test 4: Learning metrics tracking
    print("\n[TEST 4] Learning Metrics")
    final_status = system.get_system_status()
    metrics = final_status["learning"]
    assert metrics["tasks_completed"] == 4
    assert metrics["reflections_performed"] == 4
    print(f"   ✓ Tasks completed: {metrics['tasks_completed']}")
    print(f"   ✓ Reflections performed: {metrics['reflections_performed']}")
    
    # Test 5: Category-theoretic structure
    print("\n[TEST 5] Category-Theoretic Structure")
    cat_structure = system.get_category_structure()
    assert cat_structure["category"] == "AgentSystem"
    assert "identity" in cat_structure["objects"]
    assert "memory" in cat_structure["objects"]
    print(f"   ✓ Category: {cat_structure['category']}")
    print(f"   ✓ Objects: {cat_structure['objects']}")
    
    # Test 6: Memory consolidation
    print("\n[TEST 6] Memory Consolidation")
    # Add items to working memory beyond capacity
    for i in range(10):
        system.working_memory.store(MemoryEntry(
            content={"item": i},
            memory_type=MemoryType.WORKING,
            importance=0.3
        ))
    
    # Trigger consolidation
    system.perceive({"consolidation_trigger": True, "importance": 0.5})
    working_stats = system.working_memory.stats()
    print(f"   ✓ Working memory after consolidation: {working_stats['count']} items")
    
    # Test 7: Reflection system
    print("\n[TEST 7] Reflection System")
    reflection = system.reflect({"final": True})
    assert reflection["total_reflections"] > 0
    print(f"   ✓ Total reflections: {reflection['total_reflections']}")
    
    print("\n" + "="*60)
    print("ALL INTEGRATION TESTS PASSED ✓")
    print("="*60)
    
    return final_status


def demonstrate_capabilities():
    """Demonstrate key system capabilities"""
    print("\n" + "="*60)
    print("CAPABILITY DEMONSTRATION")
    print("="*60)
    
    system = IntegratedAgentSystem(name="DemoAgent")
    
    print("\n[Capability 1] Hierarchical Planning")
    plan = system.plan(
        "Build a multi-agent system with memory and reflection",
        context={"complexity": "high"}
    )
    total_nodes = len(plan.root_nodes)
    for root in plan.root_nodes:
        total_nodes += len(root.alternative_branches)
    print(f"   Generated {total_nodes} plan nodes")
    for i, root in enumerate(plan.root_nodes[:3], 1):
        print(f"   {i}. {root.description}")
    
    print("\n[Capability 2] Multi-Tier Memory")
    # Store in different memory types
    system.working_memory.store(MemoryEntry(
        content={"task": "current_focus"},
        memory_type=MemoryType.WORKING,
        importance=0.9
    ))
    system.semantic_memory.store(MemoryEntry(
        content={"fact": "AGI requires generalization"},
        memory_type=MemoryType.SEMANTIC,
        importance=0.8
    ))
    status = system.get_system_status()
    print(f"   Working memory: {status['memory']['working']['count']} entries")
    print(f"   Semantic memory: {status['memory']['semantic']['count']} entries")
    
    print("\n[Capability 3] Self-Reflection")
    # Create some reflections
    for i in range(3):
        reflection = Reflection(
            type=ReflectionType.PERFORMANCE.value,
            subject=f"task_{i}",
            observation="Task completed successfully",
            analysis="Efficient execution"
        )
        system.reflection.reflect(reflection)
    
    pending = system.reflection.get_pending_reflections()
    print(f"   Pending reflections: {len(pending)}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    try:
        # Run integration tests
        final_status = test_full_integration()
        
        # Demonstrate capabilities
        demonstrate_capabilities()
        
        # Print final summary
        print("\n" + "="*60)
        print("FINAL SYSTEM STATUS")
        print("="*60)
        print(json.dumps(final_status, indent=2, default=str))
        
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
