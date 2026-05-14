"""
Comprehensive test suite for Self-Evolving Skill Acquisition Module.

Tests cover:
1. Demonstration recording and retrieval
2. Pattern extraction from multiple demonstrations
3. Skill crystallization from demonstrations
4. Skill tree organization and dependency management
5. Skill evolution and versioning
6. Skill validation and specialization
7. End-to-end workflows
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.skill_acquisition import (
    ExecutionStep,
    SkillDemonstration,
    SkillDemonstrationRecorder,
    PatternExtractor,
    Skill,
    SkillTree,
    SkillCrystallizer,
    SkillStatus,
    SkillType,
    create_crystallizer,
    quick_crystallize
)
from datetime import datetime


# ==================== Test ExecutionStep ====================

def test_execution_step_creation():
    """Test creating execution steps."""
    step = ExecutionStep(
        step_number=1,
        action="Execute web search",
        tool_used="web_search",
        input_params={"query": "AGI research", "time_range": "week"},
        output_result={"results": 10},
        context={"user_goal": "research"}
    )
    
    assert step.step_number == 1
    assert step.action == "Execute web search"
    assert step.tool_used == "web_search"
    assert step.input_params["query"] == "AGI research"
    assert step.output_result["results"] == 10
    print("✓ ExecutionStep creation")


def test_execution_step_serialization():
    """Test execution step serialization."""
    step = ExecutionStep(
        step_number=1,
        action="Test action",
        tool_used="test_tool",
        input_params={"key": "value"},
        output_result="result",
        context={}
    )
    
    # Serialize
    data = step.to_dict()
    assert data["step_number"] == 1
    assert data["action"] == "Test action"
    assert "timestamp" in data
    
    # Deserialize
    restored = ExecutionStep.from_dict(data)
    assert restored.step_number == step.step_number
    assert restored.action == step.action
    print("✓ ExecutionStep serialization")


# ==================== Test SkillDemonstration ====================

def test_demonstration_creation():
    """Test creating skill demonstrations."""
    steps = [
        ExecutionStep(
            step_number=1,
            action="Step 1",
            tool_used="tool1",
            input_params={},
            output_result="result1",
            context={}
        ),
        ExecutionStep(
            step_number=2,
            action="Step 2",
            tool_used="tool2",
            input_params={},
            output_result="result2",
            context={}
        )
    ]
    
    demo = SkillDemonstration(
        demo_id="test_001",
        task_description="Test task",
        domain="test_domain",
        steps=steps,
        success_outcome="Success",
        performance_metrics={"accuracy": 0.95},
        context={"test": True}
    )
    
    assert demo.demo_id == "test_001"
    assert demo.task_description == "Test task"
    assert demo.domain == "test_domain"
    assert len(demo.steps) == 2
    assert demo.performance_metrics["accuracy"] == 0.95
    print("✓ SkillDemonstration creation")


def test_demonstration_fingerprint():
    """Test fingerprint generation for deduplication."""
    steps = [
        ExecutionStep(
            step_number=1,
            action="Execute search",
            tool_used="search",
            input_params={"query": "AI"},
            output_result={},
            context={}
        )
    ]
    
    demo1 = SkillDemonstration(
        demo_id="demo_1",
        task_description="Search task",
        domain="web",
        steps=steps,
        success_outcome="Results",
        performance_metrics={},
        context={}
    )
    
    demo2 = SkillDemonstration(
        demo_id="demo_2",
        task_description="Search task",
        domain="web",
        steps=steps,
        success_outcome="Different results",
        performance_metrics={"accuracy": 0.9},
        context={}
    )
    
    # Same structure should produce same fingerprint
    assert demo1.get_fingerprint() == demo2.get_fingerprint()
    print("✓ Demonstration fingerprint deduplication")


def test_demonstration_serialization():
    """Test demonstration serialization."""
    steps = [ExecutionStep(
        step_number=1,
        action="Action",
        tool_used=None,
        input_params={},
        output_result=None,
        context={}
    )]
    
    demo = SkillDemonstration(
        demo_id="test",
        task_description="Test",
        domain="test",
        steps=steps,
        success_outcome="Done",
        performance_metrics={},
        context={}
    )
    
    # Serialize
    data = demo.to_dict()
    assert data["demo_id"] == "test"
    assert len(data["steps"]) == 1
    
    # Deserialize
    restored = SkillDemonstration.from_dict(data)
    assert restored.demo_id == demo.demo_id
    assert len(restored.steps) == len(demo.steps)
    print("✓ Demonstration serialization")


# ==================== Test SkillDemonstrationRecorder ====================

def test_recorder_creation():
    """Test recorder initialization."""
    recorder = SkillDemonstrationRecorder()
    assert recorder.get_all_demonstrations() == []
    print("✓ Recorder initialization")


def test_record_demonstration():
    """Test recording demonstrations."""
    recorder = SkillDemonstrationRecorder()
    
    steps = [
        ExecutionStep(
            step_number=1,
            action="Search",
            tool_used="web_search",
            input_params={"query": "test"},
            output_result={},
            context={}
        )
    ]
    
    demo = recorder.record_demonstration(
        task_description="Web search task",
        domain="web_search",
        steps=steps,
        success_outcome="Found 5 results",
        performance_metrics={"time": 1.5, "accuracy": 0.9},
        context={"test": True}
    )
    
    assert demo.demo_id is not None
    assert len(recorder.get_all_demonstrations()) == 1
    print("✓ Recording demonstration")


def test_deduplication():
    """Test demonstration deduplication."""
    recorder = SkillDemonstrationRecorder()
    
    steps = [
        ExecutionStep(
            step_number=1,
            action="Action",
            tool_used="tool",
            input_params={},
            output_result={},
            context={}
        )
    ]
    
    # Record first
    demo1 = recorder.record_demonstration(
        task_description="Same task",
        domain="test",
        steps=steps,
        success_outcome="Result A",
        performance_metrics={"a": 1},
        context={}
    )
    
    # Try to record duplicate (same structure)
    demo2 = recorder.record_demonstration(
        task_description="Same task",
        domain="test",
        steps=steps,
        success_outcome="Result B",  # Different outcome
        performance_metrics={"b": 2},  # Different metrics
        context={}
    )
    
    # Should return existing due to fingerprint match
    assert demo1.demo_id == demo2.demo_id
    assert len(recorder.get_all_demonstrations()) == 1
    print("✓ Demonstration deduplication")


def test_find_demonstrations():
    """Test finding demonstrations by criteria."""
    recorder = SkillDemonstrationRecorder()
    
    # Add web search demo
    recorder.record_demonstration(
        task_description="Web search",
        domain="web",
        steps=[ExecutionStep(
            step_number=1,
            action="Search",
            tool_used="search",
            input_params={},
            output_result={},
            context={}
        )],
        success_outcome="Results",
        performance_metrics={"accuracy": 0.9},
        context={}
    )
    
    # Add file operation demo
    recorder.record_demonstration(
        task_description="File read",
        domain="file_ops",
        steps=[ExecutionStep(
            step_number=1,
            action="Read",
            tool_used="file_read",
            input_params={},
            output_result={},
            context={}
        )],
        success_outcome="Content",
        performance_metrics={"accuracy": 0.95},
        context={}
    )
    
    # Find by domain
    web_demos = recorder.find_demonstrations(domain="web")
    assert len(web_demos) == 1
    
    # Find by performance
    high_perf = recorder.find_demonstrations(min_performance=0.92)
    assert len(high_perf) == 1
    assert high_perf[0].domain == "file_ops"
    print("✓ Finding demonstrations")


# ==================== Test PatternExtractor ====================

def test_pattern_extraction():
    """Test extracting patterns from demonstrations."""
    extractor = PatternExtractor()
    
    # Create similar demonstrations
    demos = []
    for i in range(3):
        steps = [
            ExecutionStep(
                step_number=1,
                action="Analyze query",
                tool_used=None,
                input_params={"query": f"query_{i}"},
                output_result={},
                context={}
            ),
            ExecutionStep(
                step_number=2,
                action="Execute search",
                tool_used="web_search",
                input_params={"time_range": "week"},
                output_result={},
                context={}
            )
        ]
        
        demo = SkillDemonstration(
            demo_id=f"demo_{i}",
            task_description=f"Task {i}",
            domain="web_search",
            steps=steps,
            success_outcome="Results",
            performance_metrics={},
            context={}
        )
        demos.append(demo)
    
    pattern = extractor.extract_pattern(demos)
    
    assert "template" in pattern
    assert "parameter_schema" in pattern
    assert "required_tools" in pattern
    assert "web_search" in pattern["required_tools"]
    assert pattern["source_count"] == 3
    print("✓ Pattern extraction")


def test_empty_pattern_extraction():
    """Test pattern extraction with empty input."""
    extractor = PatternExtractor()
    
    pattern = extractor.extract_pattern([])
    assert pattern == {}
    print("✓ Empty pattern extraction")


# ==================== Test Skill ====================

def test_skill_creation():
    """Test creating skills."""
    skill = Skill(
        skill_id="test_skill_001",
        name="Test Skill",
        description="A test skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.DRAFT
    )
    
    assert skill.name == "Test Skill"
    assert skill.domain == "test"
    assert skill.skill_type == SkillType.ATOMIC
    assert skill.status == SkillStatus.DRAFT
    assert skill.usage_count == 0
    assert skill.success_rate == 0.0
    print("✓ Skill creation")


def test_skill_execution_tracking():
    """Test tracking skill executions."""
    skill = Skill(
        skill_id="test",
        name="Test",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    
    # Record successful execution
    skill.record_execution(success=True, execution_time=1.5, performance=0.9)
    assert skill.usage_count == 1
    assert skill.success_count == 1
    assert skill.success_rate == 1.0
    
    # Record failed execution
    skill.record_execution(success=False, execution_time=2.0, performance=0.3)
    assert skill.usage_count == 2
    assert skill.success_count == 1
    assert skill.success_rate == 0.5
    print("✓ Skill execution tracking")


def test_skill_maturity_score():
    """Test maturity score calculation."""
    skill = Skill(
        skill_id="test",
        name="Test",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    
    # Base maturity for ACTIVE status
    initial = skill.maturity_score
    
    # Increase usage
    for i in range(100):
        skill.record_execution(success=True, execution_time=1.0, performance=0.9)
    
    mature_score = skill.maturity_score
    assert mature_score > initial
    assert mature_score <= 1.0
    print("✓ Skill maturity scoring")


def test_skill_serialization():
    """Test skill serialization."""
    skill = Skill(
        skill_id="test",
        name="Test Skill",
        description="Test description",
        domain="test_domain",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.VALIDATED,
        tags={"test", "example"},
        dependencies={"dep1", "dep2"}
    )
    
    # Serialize
    data = skill.to_dict()
    assert data["name"] == "Test Skill"
    assert data["skill_type"] == "COMPOSITE"
    assert data["status"] == "VALIDATED"
    
    # Deserialize
    restored = Skill.from_dict(data)
    assert restored.name == skill.name
    assert restored.skill_type == skill.skill_type
    assert restored.status == skill.status
    assert restored.tags == skill.tags
    print("✓ Skill serialization")


# ==================== Test SkillTree ====================

def test_tree_creation():
    """Test skill tree initialization."""
    tree = SkillTree()
    assert tree.get_all_skills() == []
    stats = tree.get_stats()
    assert stats["total_skills"] == 0
    print("✓ Skill tree initialization")


def test_add_and_get_skill():
    """Test adding and retrieving skills."""
    tree = SkillTree()
    
    skill = Skill(
        skill_id="skill_001",
        name="Test Skill",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    
    # Add skill
    result = tree.add_skill(skill)
    assert result is True
    
    # Retrieve skill
    retrieved = tree.get_skill("skill_001")
    assert retrieved is not None
    assert retrieved.name == "Test Skill"
    
    # Try adding duplicate
    result = tree.add_skill(skill)
    assert result is False
    print("✓ Adding and retrieving skills")


def test_find_skills_by_domain():
    """Test finding skills by domain."""
    tree = SkillTree()
    
    # Add web domain skills
    tree.add_skill(Skill(
        skill_id="web_1",
        name="Web Skill 1",
        description="Test",
        domain="web",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    tree.add_skill(Skill(
        skill_id="web_2",
        name="Web Skill 2",
        description="Test",
        domain="web",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    # Add file domain skill
    tree.add_skill(Skill(
        skill_id="file_1",
        name="File Skill",
        description="Test",
        domain="file",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    web_skills = tree.find_skills(domain="web")
    assert len(web_skills) == 2
    
    file_skills = tree.find_skills(domain="file")
    assert len(file_skills) == 1
    print("✓ Finding skills by domain")


def test_find_skills_by_tags():
    """Test finding skills by tags."""
    tree = SkillTree()
    
    tree.add_skill(Skill(
        skill_id="skill_1",
        name="Skill 1",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        tags={"search", "web"}
    ))
    
    tree.add_skill(Skill(
        skill_id="skill_2",
        name="Skill 2",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        tags={"search", "file"}
    ))
    
    search_skills = tree.find_skills(tags={"search"})
    assert len(search_skills) == 2
    
    web_skills = tree.find_skills(tags={"web"})
    assert len(web_skills) == 1
    print("✓ Finding skills by tags")


def test_dependency_management():
    """Test skill dependency tracking."""
    tree = SkillTree()
    
    # Add base skill
    base = Skill(
        skill_id="base",
        name="Base",
        description="Base skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    tree.add_skill(base)
    
    # Add dependent skill
    dependent = Skill(
        skill_id="dependent",
        name="Dependent",
        description="Depends on base",
        domain="test",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.ACTIVE,
        dependencies={"base"}
    )
    tree.add_skill(dependent)
    
    # Check dependencies
    deps = tree.get_dependencies("dependent")
    assert "base" in deps
    
    # Check dependents
    dependents = tree.get_dependents("base")
    assert "dependent" in dependents
    print("✓ Dependency management")


def test_transitive_dependencies():
    """Test transitive dependency resolution."""
    tree = SkillTree()
    
    # Create chain: C depends on B, B depends on A
    tree.add_skill(Skill(
        skill_id="A",
        name="A",
        description="Base",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    tree.add_skill(Skill(
        skill_id="B",
        name="B",
        description="Depends on A",
        domain="test",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.ACTIVE,
        dependencies={"A"}
    ))
    
    tree.add_skill(Skill(
        skill_id="C",
        name="C",
        description="Depends on B",
        domain="test",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.ACTIVE,
        dependencies={"B"}
    ))
    
    all_deps = tree.get_all_dependencies("C")
    assert "B" in all_deps
    assert "A" in all_deps
    print("✓ Transitive dependencies")


def test_cycle_detection():
    """Test cycle detection in dependencies."""
    tree = SkillTree()
    
    # Add skills
    tree.add_skill(Skill(
        skill_id="A",
        name="A",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    tree.add_skill(Skill(
        skill_id="B",
        name="B",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        dependencies={"A"}
    ))
    
    # No cycle yet
    assert tree.check_dependency_cycles() is None
    
    # Create cycle: A depends on B (B already depends on A)
    # Add through the tree's dependency graph directly
    tree._dependency_graph["A"].add("B")
    
    cycle = tree.check_dependency_cycles()
    assert cycle is not None
    assert "A" in cycle and "B" in cycle
    print("✓ Cycle detection")


def test_skill_lineage():
    """Test getting skill lineage."""
    tree = SkillTree()
    
    # Create parent
    parent = Skill(
        skill_id="parent",
        name="Parent",
        description="Parent skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    tree.add_skill(parent)
    
    # Create child
    child = Skill(
        skill_id="child",
        name="Child",
        description="Child skill",
        domain="test",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.ACTIVE,
        parent_skill="parent"
    )
    tree.add_skill(child)
    parent.sub_skills.append("child")
    
    # Get lineage
    lineage = tree.get_skill_lineage("child")
    assert len(lineage) == 2
    assert lineage[0].skill_id == "parent"
    assert lineage[1].skill_id == "child"
    print("✓ Skill lineage")


def test_subtree():
    """Test getting subtrees."""
    tree = SkillTree()
    
    # Create hierarchy
    root = Skill(
        skill_id="root",
        name="Root",
        description="Root skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    tree.add_skill(root)
    
    child1 = Skill(
        skill_id="child1",
        name="Child 1",
        description="Child",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        parent_skill="root"
    )
    tree.add_skill(child1)
    root.sub_skills.append("child1")
    
    child2 = Skill(
        skill_id="child2",
        name="Child 2",
        description="Child",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        parent_skill="root"
    )
    tree.add_skill(child2)
    root.sub_skills.append("child2")
    
    subtree = tree.get_subtree("root")
    assert len(subtree) == 3
    ids = [s.skill_id for s in subtree]
    assert "root" in ids
    assert "child1" in ids
    assert "child2" in ids
    print("✓ Subtree retrieval")


def test_remove_skill():
    """Test skill removal."""
    tree = SkillTree()
    
    tree.add_skill(Skill(
        skill_id="A",
        name="A",
        description="Test",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    # Can remove standalone skill
    result = tree.remove_skill("A")
    assert result is True
    assert tree.get_skill("A") is None
    
    # Cannot remove non-existent skill
    result = tree.remove_skill("nonexistent")
    assert result is False
    print("✓ Skill removal")


def test_remove_with_dependents():
    """Test that skills with dependents cannot be removed."""
    tree = SkillTree()
    
    tree.add_skill(Skill(
        skill_id="base",
        name="Base",
        description="Base",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    tree.add_skill(Skill(
        skill_id="dependent",
        name="Dependent",
        description="Depends on base",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE,
        dependencies={"base"}
    ))
    
    # Cannot remove base because dependent depends on it
    result = tree.remove_skill("base")
    assert result is False
    print("✓ Removal blocked by dependents")


# ==================== Test SkillCrystallizer ====================

def test_crystallizer_creation():
    """Test crystallizer initialization."""
    crystallizer = create_crystallizer()
    assert crystallizer.recorder is not None
    assert crystallizer.extractor is not None
    assert crystallizer.skill_tree is not None
    print("✓ Crystallizer initialization")


def test_crystallize_skill():
    """Test skill crystallization from demonstrations."""
    crystallizer = create_crystallizer()
    
    # Record multiple similar demonstrations
    demo_ids = []
    for i in range(3):
        steps = [
            ExecutionStep(
                step_number=1,
                action="Analyze intent",
                tool_used=None,
                input_params={"query": f"query_{i}"},
                output_result={},
                context={}
            ),
            ExecutionStep(
                step_number=2,
                action="Execute search",
                tool_used="web_search",
                input_params={"range": "week"},
                output_result={},
                context={}
            )
        ]
        
        demo = crystallizer.recorder.record_demonstration(
            task_description=f"Research task {i}",
            domain="research",
            steps=steps,
            success_outcome="Results",
            performance_metrics={"accuracy": 0.9},
            context={}
        )
        demo_ids.append(demo.demo_id)
    
    # Crystallize
    skill = crystallizer.crystallize_skill(
        demo_ids=demo_ids,
        name="Research Skill",
        description="Execute structured research tasks",
        tags={"research", "web"}
    )
    
    assert skill is not None
    assert skill.name == "Research Skill"
    assert skill.domain == "research"
    assert skill.skill_type == SkillType.COMPOSITE
    assert skill.status == SkillStatus.DRAFT
    assert "web_search" in skill.required_tools
    assert "research" in skill.tags
    print("✓ Skill crystallization")


def test_crystallize_single_demo():
    """Test crystallizing from single demonstration (atomic skill)."""
    crystallizer = create_crystallizer()
    
    steps = [ExecutionStep(
        step_number=1,
        action="Calculate",
        tool_used="calculator",
        input_params={"expr": "2+2"},
        output_result=4,
        context={}
    )]
    
    demo = crystallizer.recorder.record_demonstration(
        task_description="Calculate sum",
        domain="math",
        steps=steps,
        success_outcome=4,
        performance_metrics={},
        context={}
    )
    
    skill = crystallizer.crystallize_skill(
        demo_ids=[demo.demo_id],
        name="Calculator",
        description="Perform calculations"
    )
    
    assert skill is not None
    assert skill.skill_type == SkillType.ATOMIC
    print("✓ Atomic skill crystallization")


def test_skill_validation():
    """Test skill validation."""
    crystallizer = create_crystallizer()
    
    # Add a base skill first (will be a dependency)
    base_skill = Skill(
        skill_id="base_tool_skill",
        name="Base Tool",
        description="Base tool as skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    crystallizer.skill_tree.add_skill(base_skill)
    
    # Create skill that depends on the base skill
    steps = [
        ExecutionStep(
            step_number=1,
            action="Search",
            tool_used=None,  # No tool dependency for this test
            input_params={},
            output_result={},
            context={}
        )
    ]
    
    demo = crystallizer.recorder.record_demonstration(
        task_description="Test",
        domain="test",
        steps=steps,
        success_outcome="Done",
        performance_metrics={},
        context={}
    )
    
    skill = crystallizer.crystallize_skill(
        demo_ids=[demo.demo_id],
        name="Test Skill",
        description="Test"
    )
    
    # Manually add dependency to test validation
    skill.dependencies.add("base_tool_skill")
    crystallizer.skill_tree._dependency_graph[skill.skill_id].add("base_tool_skill")
    
    success, results = crystallizer.validate_skill(
        skill.skill_id,
        test_contexts=[{"test": True}]
    )
    
    assert "tests_run" in results
    assert "dependencies_ok" in results
    print("✓ Skill validation")


def test_skill_evolution():
    """Test skill evolution with new demonstrations."""
    crystallizer = create_crystallizer()
    
    # Create original skill
    steps = [ExecutionStep(
        step_number=1,
        action="Action",
        tool_used="tool",
        input_params={},
        output_result={},
        context={}
    )]
    
    demo1 = crystallizer.recorder.record_demonstration(
        task_description="Original",
        domain="evolution",
        steps=steps,
        success_outcome="Done",
        performance_metrics={},
        context={}
    )
    
    original = crystallizer.crystallize_skill(
        demo_ids=[demo1.demo_id],
        name="Evolving Skill",
        description="Will evolve"
    )
    
    # Record new demonstration
    demo2 = crystallizer.recorder.record_demonstration(
        task_description="Enhanced",
        domain="evolution",
        steps=steps,
        success_outcome="Better result",
        performance_metrics={"accuracy": 0.95},
        context={}
    )
    
    # Evolve skill
    evolved = crystallizer.evolve_skill(
        original.skill_id,
        new_demonstrations=[demo2.demo_id],
        improved_description="Enhanced skill with better performance"
    )
    
    assert evolved is not None
    assert evolved.version == 2
    assert original.skill_id in evolved.previous_versions
    assert original.status == SkillStatus.DEPRECATED
    assert evolved.description == "Enhanced skill with better performance"
    print("✓ Skill evolution")


def test_specialize_skill():
    """Test skill specialization."""
    crystallizer = create_crystallizer()
    
    # Create base skill
    steps = [ExecutionStep(
        step_number=1,
        action="Search",
        tool_used="search",
        input_params={},
        output_result={},
        context={}
    )]
    
    demo = crystallizer.recorder.record_demonstration(
        task_description="Search",
        domain="web",
        steps=steps,
        success_outcome="Results",
        performance_metrics={},
        context={}
    )
    
    base = crystallizer.crystallize_skill(
        demo_ids=[demo.demo_id],
        name="Base Search",
        description="Generic search"
    )
    
    # Create specialization
    specialized = crystallizer.specialize_skill(
        skill_id=base.skill_id,
        specialization_name="Academic Search",
        specialization_desc="Search academic papers",
        specific_context={"sources": ["arxiv", "scholar"]}
    )
    
    assert specialized is not None
    assert specialized.name == "Academic Search"
    assert specialized.parent_skill == base.skill_id
    assert "specialized" in specialized.tags
    # Specialized skill should be in base's sub_skills
    assert specialized.skill_id in base.sub_skills
    print("✓ Skill specialization")


# ==================== Test Convenience Functions ====================

def test_quick_crystallize():
    """Test the quick crystallize convenience function."""
    steps = [
        ExecutionStep(
            step_number=1,
            action="Analyze",
            tool_used=None,
            input_params={},
            output_result={},
            context={}
        ),
        ExecutionStep(
            step_number=2,
            action="Execute",
            tool_used="tool",
            input_params={},
            output_result={},
            context={}
        )
    ]
    
    demos = [
        SkillDemonstration(
            demo_id="demo_1",
            task_description="Task A",
            domain="test",
            steps=steps,
            success_outcome="Done",
            performance_metrics={},
            context={}
        ),
        SkillDemonstration(
            demo_id="demo_2",
            task_description="Task B",
            domain="test",
            steps=steps,
            success_outcome="Done",
            performance_metrics={},
            context={}
        )
    ]
    
    skill = quick_crystallize(demos, "Quick Skill", "Quickly created")
    
    assert skill is not None
    assert skill.name == "Quick Skill"
    assert skill.domain == "test"
    print("✓ Quick crystallize function")


# ==================== Test Integration & Edge Cases ====================

def test_empty_demonstration_crystallization():
    """Test crystallization fails with no demonstrations."""
    crystallizer = create_crystallizer()
    
    skill = crystallizer.crystallize_skill(
        demo_ids=["nonexistent"],
        name="Fail",
        description="Should fail"
    )
    
    assert skill is None
    print("✓ Empty demonstration handling")


def test_skill_tree_stats():
    """Test skill tree statistics."""
    tree = SkillTree()
    
    # Add skills of different types and statuses
    tree.add_skill(Skill(
        skill_id="s1",
        name="S1",
        description="Test",
        domain="web",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    ))
    
    tree.add_skill(Skill(
        skill_id="s2",
        name="S2",
        description="Test",
        domain="web",
        skill_type=SkillType.COMPOSITE,
        status=SkillStatus.DRAFT
    ))
    
    tree.add_skill(Skill(
        skill_id="s3",
        name="S3",
        description="Test",
        domain="file",
        skill_type=SkillType.META,
        status=SkillStatus.VALIDATED
    ))
    
    stats = tree.get_stats()
    
    assert stats["total_skills"] == 3
    assert stats["by_status"]["ACTIVE"] == 1
    assert stats["by_status"]["DRAFT"] == 1
    assert stats["by_status"]["VALIDATED"] == 1
    assert stats["by_type"]["ATOMIC"] == 1
    assert stats["by_type"]["COMPOSITE"] == 1
    assert stats["by_type"]["META"] == 1
    assert stats["by_domain"]["web"] == 2
    assert stats["by_domain"]["file"] == 1
    assert stats["cycle_detected"] is False
    print("✓ Skill tree statistics")


def test_mature_skill_filtering():
    """Test filtering skills by maturity."""
    tree = SkillTree()
    
    # Add new skill
    new_skill = Skill(
        skill_id="new",
        name="New",
        description="New skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.DRAFT
    )
    tree.add_skill(new_skill)
    
    # Add mature skill
    mature_skill = Skill(
        skill_id="mature",
        name="Mature",
        description="Mature skill",
        domain="test",
        skill_type=SkillType.ATOMIC,
        status=SkillStatus.ACTIVE
    )
    # Simulate usage
    for _ in range(100):
        mature_skill.record_execution(True, 1.0, 0.95)
    tree.add_skill(mature_skill)
    
    # Find mature skills
    mature = tree.find_skills(min_maturity=0.5)
    assert len(mature) == 1
    assert mature[0].skill_id == "mature"
    print("✓ Maturity-based filtering")


def test_complex_pattern_extraction():
    """Test pattern extraction with varied demonstrations."""
    extractor = PatternExtractor()
    
    # Create varied but similar demonstrations
    demos = []
    for i in range(5):
        # Varying step counts and tools
        steps = [
            ExecutionStep(
                step_number=1,
                action="Start",
                tool_used=None,
                input_params={"start_param": i},
                output_result={},
                context={}
            )
        ]
        
        # 60% have middle step
        if i < 3:
            steps.append(ExecutionStep(
                step_number=2,
                action="Process",
                tool_used="processor",
                input_params={},
                output_result={},
                context={}
            ))
        
        steps.append(ExecutionStep(
            step_number=len(steps) + 1,
            action="Finish",
            tool_used="finisher",
            input_params={},
            output_result={},
            context={}
        ))
        
        demo = SkillDemonstration(
            demo_id=f"var_{i}",
            task_description=f"Varied {i}",
            domain="varied",
            steps=steps,
            success_outcome="Done",
            performance_metrics={},
            context={"var": i}
        )
        demos.append(demo)
    
    pattern = extractor.extract_pattern(demos)
    
    assert "template" in pattern
    assert pattern["source_count"] == 5
    assert "finisher" in pattern["required_tools"]  # Used in 100%
    # processor used in 60%, may or may not be included based on threshold
    print("✓ Complex pattern extraction")


def test_skill_parameter_schema():
    """Test that parameter schema is extracted correctly."""
    extractor = PatternExtractor()
    
    demos = []
    for i in range(3):
        # Create params dict where required_param is always present
        # and optional_param is missing in the last demo (not None, but absent)
        input_params = {"required_param": f"val_{i}"}
        if i < 2:  # Only add optional_param in first 2 demos
            input_params["optional_param"] = i
        
        steps = [ExecutionStep(
            step_number=1,
            action="Action",
            tool_used="tool",
            input_params=input_params,
            output_result={},
            context={}
        )]
        
        demo = SkillDemonstration(
            demo_id=f"demo_{i}",
            task_description="Test",
            domain="test",
            steps=steps,
            success_outcome="Done",
            performance_metrics={},
            context={}
        )
        demos.append(demo)
    
    pattern = extractor.extract_pattern(demos)
    schema = pattern["parameter_schema"]
    
    # Both params should be detected
    assert "required_param" in schema
    assert schema["required_param"]["frequency"] == 1.0
    
    # optional_param should have frequency 2/3 since missing in 1 demo
    assert "optional_param" in schema
    assert schema["optional_param"]["frequency"] < 1.0
    print("✓ Parameter schema extraction")


def run_all_tests():
    """Run all tests."""
    tests = [
        # ExecutionStep tests
        test_execution_step_creation,
        test_execution_step_serialization,
        
        # SkillDemonstration tests
        test_demonstration_creation,
        test_demonstration_fingerprint,
        test_demonstration_serialization,
        
        # Recorder tests
        test_recorder_creation,
        test_record_demonstration,
        test_deduplication,
        test_find_demonstrations,
        
        # PatternExtractor tests
        test_pattern_extraction,
        test_empty_pattern_extraction,
        
        # Skill tests
        test_skill_creation,
        test_skill_execution_tracking,
        test_skill_maturity_score,
        test_skill_serialization,
        
        # SkillTree tests
        test_tree_creation,
        test_add_and_get_skill,
        test_find_skills_by_domain,
        test_find_skills_by_tags,
        test_dependency_management,
        test_transitive_dependencies,
        test_cycle_detection,
        test_skill_lineage,
        test_subtree,
        test_remove_skill,
        test_remove_with_dependents,
        test_skill_tree_stats,
        test_mature_skill_filtering,
        
        # Crystallizer tests
        test_crystallizer_creation,
        test_crystallize_skill,
        test_crystallize_single_demo,
        test_skill_validation,
        test_skill_evolution,
        test_specialize_skill,
        
        # Convenience functions
        test_quick_crystallize,
        
        # Integration & edge cases
        test_empty_demonstration_crystallization,
        test_complex_pattern_extraction,
        test_skill_parameter_schema,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 60)
    print("Self-Evolving Skill Acquisition Test Suite")
    print("=" * 60)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__}: {e}")
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
