"""
Tests for Workflow Orchestrator

Validates:
- Workflow creation and management
- Step execution with dependencies
- Skill registry integration
- Error handling and retries
- Metrics tracking
"""

import pytest
import asyncio
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.workflow_orchestrator import (
    WorkflowOrchestrator, WorkflowContext, WorkflowStep,
    WorkflowStatus, StepStatus, WorkflowResult,
    create_orchestrator, run_autonomous_workflow
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def orchestrator():
    """Create a basic orchestrator for testing."""
    return WorkflowOrchestrator()


@pytest.fixture
def orchestrator_with_skills():
    """Create an orchestrator with sample skills."""
    skills = {
        "echo": lambda msg: {"echo": msg},
        "add": lambda a, b: {"result": a + b},
        "fail_once": lambda: exec('raise Exception("Intentional failure")'),
        "async_echo": lambda msg: {"async_echo": msg}
    }
    return WorkflowOrchestrator(skill_registry=skills)


@pytest.fixture
def sample_workflow(orchestrator):
    """Create a sample workflow for testing."""
    context = orchestrator.create_workflow(
        goal="Test workflow",
        constraints=["test"]
    )
    return context


# ============================================================================
# Workflow Creation Tests
# ============================================================================

class TestWorkflowCreation:
    """Test workflow context creation."""
    
    def test_create_workflow_basic(self, orchestrator):
        """Test basic workflow creation."""
        context = orchestrator.create_workflow(
            goal="Test goal",
            constraints=["c1", "c2"]
        )
        
        assert context.goal == "Test goal"
        assert context.constraints == ["c1", "c2"]
        assert context.workflow_id is not None
        assert len(context.workflow_id) > 0
        assert context.workflow_id in orchestrator.active_workflows
        assert context.workflow_id in orchestrator.workflow_steps
        assert orchestrator.workflow_status[context.workflow_id] == WorkflowStatus.PENDING
    
    def test_create_workflow_with_variables(self, orchestrator):
        """Test workflow creation with initial variables."""
        context = orchestrator.create_workflow(
            goal="Test",
            initial_variables={"key1": "value1", "number": 42}
        )
        
        assert context.variables["key1"] == "value1"
        assert context.variables["number"] == 42
    
    def test_workflow_id_unique(self, orchestrator):
        """Test that workflow IDs are unique."""
        ctx1 = orchestrator.create_workflow(goal="Goal 1")
        ctx2 = orchestrator.create_workflow(goal="Goal 2")
        
        assert ctx1.workflow_id != ctx2.workflow_id


# ============================================================================
# Step Management Tests
# ============================================================================

class TestStepManagement:
    """Test workflow step operations."""
    
    def test_add_step_basic(self, orchestrator, sample_workflow):
        """Test adding a step to workflow."""
        step_id = orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Test step",
            action_type="skill",
            target="echo"
        )
        
        assert step_id is not None
        steps = orchestrator.workflow_steps[sample_workflow.workflow_id]
        assert len(steps) == 1
        assert steps[0].description == "Test step"
        assert steps[0].action_type == "skill"
        assert steps[0].status == StepStatus.PENDING
    
    def test_add_step_with_parameters(self, orchestrator, sample_workflow):
        """Test adding a step with parameters."""
        step_id = orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Step with params",
            action_type="skill",
            target="add",
            parameters={"a": 5, "b": 3}
        )
        
        steps = orchestrator.workflow_steps[sample_workflow.workflow_id]
        assert steps[0].parameters == {"a": 5, "b": 3}
    
    def test_add_step_with_dependencies(self, orchestrator, sample_workflow):
        """Test adding steps with dependencies."""
        step1_id = orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Step 1",
            action_type="skill",
            target="echo"
        )
        
        step2_id = orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Step 2",
            action_type="skill",
            target="echo",
            dependencies=[step1_id]
        )
        
        steps = orchestrator.workflow_steps[sample_workflow.workflow_id]
        assert steps[1].dependencies == [step1_id]
    
    def test_add_step_invalid_workflow(self, orchestrator):
        """Test adding step to non-existent workflow."""
        with pytest.raises(ValueError, match="Workflow.*not found"):
            orchestrator.add_step(
                workflow_id="invalid-id",
                description="Test",
                action_type="skill",
                target="echo"
            )
    
    def test_generate_plan_steps(self, orchestrator, sample_workflow):
        """Test automatic plan generation."""
        steps = orchestrator.generate_plan_steps(sample_workflow.workflow_id)
        
        assert len(steps) > 0
        assert steps[0].action_type == "reasoning"
        assert any(step.action_type == "skill" for step in steps)


# ============================================================================
# Skill Registry Tests
# ============================================================================

class TestSkillRegistry:
    """Test skill registration and management."""
    
    def test_register_skill(self, orchestrator):
        """Test skill registration."""
        def test_skill(x):
            return {"result": x * 2}
        
        orchestrator.register_skill("double", test_skill)
        
        assert "double" in orchestrator.skill_registry
        assert orchestrator.skill_registry["double"](5) == {"result": 10}
    
    def test_register_multiple_skills(self, orchestrator):
        """Test registering multiple skills."""
        orchestrator.register_skill("s1", lambda: 1)
        orchestrator.register_skill("s2", lambda: 2)
        orchestrator.register_skill("s3", lambda: 3)
        
        assert len(orchestrator.skill_registry) == 3
    
    def test_orchestrator_with_skills_fixture(self, orchestrator_with_skills):
        """Test orchestrator with pre-configured skills."""
        assert "echo" in orchestrator_with_skills.skill_registry
        assert "add" in orchestrator_with_skills.skill_registry


# ============================================================================
# Step Execution Tests
# ============================================================================

class TestStepExecution:
    """Test step execution functionality."""
    
    @pytest.mark.asyncio
    async def test_execute_skill_step(self, orchestrator_with_skills):
        """Test executing a skill step."""
        sample_workflow = orchestrator_with_skills.create_workflow(goal="Test workflow")
        orchestrator_with_skills.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Echo step",
            action_type="skill",
            target="echo",
            parameters={"msg": "hello"}
        )
        
        steps = orchestrator_with_skills.workflow_steps[sample_workflow.workflow_id]
        result = await orchestrator_with_skills._execute_step(steps[0], sample_workflow)
        
        assert result is True
        assert steps[0].status == StepStatus.COMPLETED
        assert steps[0].result == {"echo": "hello"}
    
    @pytest.mark.asyncio
    async def test_execute_skill_with_add(self, orchestrator_with_skills):
        """Test executing add skill."""
        sample_workflow = orchestrator_with_skills.create_workflow(goal="Test workflow")
        orchestrator_with_skills.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Add step",
            action_type="skill",
            target="add",
            parameters={"a": 10, "b": 20}
        )
        
        steps = orchestrator_with_skills.workflow_steps[sample_workflow.workflow_id]
        result = await orchestrator_with_skills._execute_step(steps[0], sample_workflow)
        
        assert result is True
        assert steps[0].result == {"result": 30}
    
    @pytest.mark.asyncio
    async def test_execute_missing_skill(self, orchestrator, sample_workflow):
        """Test executing non-existent skill."""
        orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Missing skill",
            action_type="skill",
            target="nonexistent",
            parameters={}
        )
        
        steps = orchestrator.workflow_steps[sample_workflow.workflow_id]
        result = await orchestrator._execute_step(steps[0], sample_workflow)
        
        assert result is True  # Step completes but with error result
        assert "error" in steps[0].result
    
    @pytest.mark.asyncio
    async def test_execute_memory_operation(self, orchestrator, sample_workflow):
        """Test memory operation execution."""
        orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Memory op",
            action_type="memory",
            target="store",
            parameters={"key": "value"}
        )
        
        steps = orchestrator.workflow_steps[sample_workflow.workflow_id]
        result = await orchestrator._execute_step(steps[0], sample_workflow)
        
        assert result is True
        assert steps[0].status == StepStatus.COMPLETED


# ============================================================================
# Workflow Execution Tests
# ============================================================================

class TestWorkflowExecution:
    """Test full workflow execution."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, orchestrator_with_skills):
        """Test executing a simple workflow."""
        ctx = orchestrator_with_skills.create_workflow(goal="Test workflow")
        
        orchestrator_with_skills.add_step(
            workflow_id=ctx.workflow_id,
            description="Echo step",
            action_type="skill",
            target="echo",
            parameters={"msg": "hello world"}
        )
        
        result = await orchestrator_with_skills.execute_workflow(ctx.workflow_id)
        
        assert result.success is True
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 1
        assert result.steps_failed == 0
    
    @pytest.mark.asyncio
    async def test_execute_workflow_with_dependencies(self, orchestrator_with_skills):
        """Test workflow with step dependencies."""
        ctx = orchestrator_with_skills.create_workflow(goal="Dependency test")
        
        step1 = orchestrator_with_skills.add_step(
            workflow_id=ctx.workflow_id,
            description="Step 1",
            action_type="skill",
            target="add",
            parameters={"a": 5, "b": 5}
        )
        
        orchestrator_with_skills.add_step(
            workflow_id=ctx.workflow_id,
            description="Step 2",
            action_type="skill",
            target="echo",
            parameters={"msg": "step2"},
            dependencies=[step1]
        )
        
        result = await orchestrator_with_skills.execute_workflow(ctx.workflow_id)
        
        assert result.success is True
        assert result.steps_completed == 2
    
    @pytest.mark.asyncio
    async def test_execute_empty_workflow(self, orchestrator):
        """Test executing empty workflow (auto-generates steps)."""
        ctx = orchestrator.create_workflow(goal="Auto plan test")
        
        result = await orchestrator.execute_workflow(ctx.workflow_id)
        
        # Should generate plan and execute
        assert result.workflow_id == ctx.workflow_id
        assert result.execution_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_workflow(self, orchestrator):
        """Test executing non-existent workflow."""
        result = await orchestrator.execute_workflow("invalid-id")
        
        assert result.success is False
        assert result.status == WorkflowStatus.FAILED
        assert "Workflow not found" in result.errors


# ============================================================================
# Parameter Resolution Tests
# ============================================================================

class TestParameterResolution:
    """Test parameter template resolution."""
    
    def test_resolve_simple_parameters(self, orchestrator):
        """Test resolving simple parameters."""
        context = WorkflowContext(variables={"name": "test"})
        params = {"key": "value", "name": "$name"}
        
        resolved = orchestrator._resolve_parameters(params, context)
        
        assert resolved["key"] == "value"
        assert resolved["name"] == "test"
    
    def test_resolve_step_results(self, orchestrator):
        """Test resolving step result references."""
        context = WorkflowContext()
        context.step_results["step1"] = "result1"
        
        params = {"ref": "$step1"}
        resolved = orchestrator._resolve_parameters(params, context)
        
        assert resolved["ref"] == "result1"
    
    def test_resolve_unknown_variable(self, orchestrator):
        """Test resolving unknown variable."""
        context = WorkflowContext()
        params = {"ref": "$unknown"}
        
        resolved = orchestrator._resolve_parameters(params, context)
        
        # Should keep original value
        assert resolved["ref"] == "$unknown"


# ============================================================================
# Agentic Workflow Tests
# ============================================================================

class TestAgenticWorkflow:
    """Test agentic workflow creation patterns."""
    
    def test_create_research_workflow(self, orchestrator):
        """Test creating a research workflow."""
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Research the latest AI breakthroughs",
            require_verification=True
        )
        
        steps = orchestrator.workflow_steps[workflow_id]
        
        # Should have research-specific steps
        assert len(steps) >= 3
        assert any("research" in s.description.lower() or 
                  "search" in s.description.lower() for s in steps)
    
    def test_create_code_workflow(self, orchestrator):
        """Test creating a code generation workflow."""
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Implement a binary search tree in Python",
            require_verification=True
        )
        
        steps = orchestrator.workflow_steps[workflow_id]
        
        # Should have code-specific steps
        assert any("code" in s.description.lower() or 
                  "implement" in s.description.lower() or
                  "generate" in s.description.lower() for s in steps)
    
    def test_create_analysis_workflow(self, orchestrator):
        """Test creating an analysis workflow."""
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Analyze sales data for Q1 2026"
        )
        
        steps = orchestrator.workflow_steps[workflow_id]
        
        # Should have analysis-specific steps
        assert any("analysis" in s.description.lower() or 
                  "data" in s.description.lower() or
                  "gather" in s.description.lower() for s in steps)
    
    def test_create_default_workflow(self, orchestrator):
        """Test creating a default workflow for unknown goal types."""
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Do something unspecified"
        )
        
        steps = orchestrator.workflow_steps[workflow_id]
        
        # Should have at least one step
        assert len(steps) >= 1


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetrics:
    """Test metrics tracking."""
    
    def test_initial_metrics(self, orchestrator):
        """Test initial metrics state."""
        metrics = orchestrator.get_metrics()
        
        assert metrics["total_workflows"] == 0
        assert metrics["successful"] == 0
        assert metrics["failed"] == 0
        assert metrics["success_rate_percent"] == 0.0
    
    @pytest.mark.asyncio
    async def test_metrics_after_execution(self, orchestrator_with_skills):
        """Test metrics after workflow execution."""
        ctx = orchestrator_with_skills.create_workflow(goal="Metrics test")
        orchestrator_with_skills.add_step(
            workflow_id=ctx.workflow_id,
            description="Test step",
            action_type="skill",
            target="echo",
            parameters={"msg": "test"}
        )
        
        await orchestrator_with_skills.execute_workflow(ctx.workflow_id)
        
        metrics = orchestrator_with_skills.get_metrics()
        
        assert metrics["total_workflows"] == 1
        assert metrics["successful"] == 1
        assert metrics["success_rate_percent"] == 100.0


# ============================================================================
# Status and Retrieval Tests
# ============================================================================

class TestStatusRetrieval:
    """Test status and data retrieval."""
    
    def test_get_workflow_status(self, orchestrator, sample_workflow):
        """Test getting workflow status."""
        status = orchestrator.get_workflow_status(sample_workflow.workflow_id)
        
        assert status == WorkflowStatus.PENDING
    
    def test_get_workflow_status_invalid(self, orchestrator):
        """Test getting status of non-existent workflow."""
        status = orchestrator.get_workflow_status("invalid")
        
        assert status is None
    
    def test_get_workflow_steps(self, orchestrator, sample_workflow):
        """Test getting workflow steps."""
        orchestrator.add_step(
            workflow_id=sample_workflow.workflow_id,
            description="Step 1",
            action_type="skill",
            target="echo"
        )
        
        steps = orchestrator.get_workflow_steps(sample_workflow.workflow_id)
        
        assert len(steps) == 1
        assert steps[0]["description"] == "Step 1"


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestFactoryFunctions:
    """Test convenience factory functions."""
    
    def test_create_orchestrator(self):
        """Test create_orchestrator factory."""
        skills = {"test": lambda: "result"}
        orch = create_orchestrator(skills)
        
        assert isinstance(orch, WorkflowOrchestrator)
        assert "test" in orch.skill_registry
    
    @pytest.mark.asyncio
    async def test_run_autonomous_workflow(self):
        """Test run_autonomous_workflow one-shot function."""
        skills = {"echo": lambda msg: {"message": msg}}
        
        result = await run_autonomous_workflow(
            goal="Echo test message",
            skills=skills,
            require_verification=False
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.workflow_id is not None


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Test data serialization."""
    
    def test_workflow_step_to_dict(self):
        """Test WorkflowStep serialization."""
        step = WorkflowStep(
            description="Test step",
            action_type="skill",
            target="echo",
            parameters={"msg": "hello"}
        )
        
        d = step.to_dict()
        
        assert d["description"] == "Test step"
        assert d["action_type"] == "skill"
        assert d["target"] == "echo"
        assert d["parameters"] == {"msg": "hello"}
        assert "step_id" in d
    
    def test_workflow_context_to_dict(self):
        """Test WorkflowContext serialization."""
        ctx = WorkflowContext(
            goal="Test",
            variables={"key": "value"}
        )
        
        d = ctx.to_dict()
        
        assert d["goal"] == "Test"
        assert d["variables"] == {"key": "value"}
        assert "workflow_id" in d
    
    def test_workflow_result_to_dict(self):
        """Test WorkflowResult serialization."""
        result = WorkflowResult(
            workflow_id="wf-123",
            success=True,
            steps_completed=5
        )
        
        d = result.to_dict()
        
        assert d["workflow_id"] == "wf-123"
        assert d["success"] is True
        assert d["steps_completed"] == 5


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_research_workflow_execution(self):
        """Test complete research workflow execution."""
        skills = {
            "web_search": lambda query: {"results": [f"Result for {query}"]},
            "analysis": lambda task, input: {"analysis": f"Analyzed {task}"}
        }
        
        orchestrator = create_orchestrator(skills)
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Research quantum computing breakthroughs",
            require_verification=False
        )
        
        result = await orchestrator.execute_workflow(workflow_id)
        
        assert result.success is True
        assert result.steps_completed >= 2
    
    @pytest.mark.asyncio
    async def test_code_workflow_execution(self):
        """Test complete code workflow execution."""
        skills = {
            "code_generation": lambda task: {"code": f"# Code for {task}"}
        }
        
        orchestrator = create_orchestrator(skills)
        workflow_id = orchestrator.create_agentic_workflow(
            goal="Implement quicksort in Python",
            require_verification=False
        )
        
        result = await orchestrator.execute_workflow(workflow_id)
        
        assert result.workflow_id == workflow_id
        assert result.execution_time_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
