"""
Tests for AgentLoop <-> CEF substrate bridge.

This is the wiring test suite for the loop-level integration of the
CEF (Constraint-Evading Fabrication / Computational Escape of Thought)
substrate into the AgentLoop orchestrator. The substrate already
provides per-output detection (cef_detector), session-level detection
(cef_session), and bridge helpers (cef_substrate_integration). This
test suite verifies that AgentLoop.run() actually USES those helpers.

The contract being tested:

  1. When `cef_session_detector` is None, the loop behaves exactly as
     before: no CEF folded steps, no overrides, no extra attributes.

  2. When `cef_session_detector` is set, every act -> observe cycle
     folds through `fold_step_into_cef`, appends a CEFLoopStep to
     `loop.cef_steps`, and exposes `loop.cef_session_verdict`.

  3. The CEF recommended loop action OVERRIDES the verifier verdict:
       - "halt"   -> Verdict.HALT
       - "freeze" -> Verdict.ESCALATE (unless verifier already HALT)
       - "restart"-> Verdict.ESCALATE (unless verifier already HALT)
       - "warn"   -> evidence-only, no verdict change
       - "continue" -> no override

  4. The override is *additive only*: a CEF "warn" on a HALT verdict
     stays HALT. A CEF "continue" on a clean CONTINUE stays CONTINUE.

  5. Per-output CRITICAL (CET) escalates to HALT regardless of the
     session verdict (the agent faking its own crash is a hard halt).

  6. The audit trail includes the CEF step data on EVALUATE steps
     (either as rationale prefix or evidence, never silently).

  7. The CEF wiring is opt-in and lazy-import-safe: the loop still
     works when the CEF substrate is not installed (returns None for
     `cef_enabled`).

These tests deliberately exercise both *negative* paths (CEF disabled
yields identical behavior to the pre-bridge loop) and *positive* paths
(the CEF override actually fires under each severity tier). The
fixture agents are tiny pure functions so the tests are deterministic
and do not require LLM calls.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.agent_loop import (
    AgentIdentity,
    AgentLoop,
    AgentLoopConfig,
    LoopBudget,
    LoopStep,
    Verdict,
    VerifierProtocol,
    LifecycleState,
    create_agent_loop,
    _extract_agent_output,
)
from core.cef_session import CEFSessionDetector, CEFSessionConfig
from core.cef_substrate_integration import (
    CEFIntegrationConfig,
    CEFLoopStep,
    fold_step_into_cef,
    record_cef_to_ledger,
)


# --------------------------------------------------------------------------
# Fixtures: tiny work agents that produce predictable CEF inputs
# --------------------------------------------------------------------------


def _make_identity() -> AgentIdentity:
    return AgentIdentity(
        loop_id="loop-cef-bridge-test",
        principal="tester",
        purpose="Verify CEF<->AgentLoop bridge",
    )


def _make_budget() -> LoopBudget:
    return LoopBudget(
        max_steps=20, max_tokens=10000, max_cost_estimate=10.0, max_wall_time_s=60.0
    )


class _FixedVerifier:
    """A verifier that always returns a single fixed verdict.

    Tests use this to verify the CEF override behavior in isolation:
    the verifier says "CONTINUE" or "HALT" predictably, and the CEF
    override is the only thing that changes the verdict.
    """

    def __init__(self, fixed: Verdict = Verdict.CONTINUE, rationale: str = "ok"):
        self._fixed = fixed
        self._rationale = rationale
        self.calls: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []

    @property
    def name(self) -> str:
        return "fixed"

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        self.calls.append((action, observation))
        return (self._fixed, self._rationale, [])


class _TickAgent:
    """A work function that ticks for a fixed number of steps then returns a goal."""

    def __init__(self, outputs: List[str], goal_after: Optional[int] = None):
        # outputs[i] is what step i produces as `agent_output`
        self._outputs = list(outputs)
        self._goal_after = goal_after
        self._idx = 0

    def __call__(self, identity: AgentIdentity, action: Dict[str, Any]) -> Dict[str, Any]:
        idx = self._idx
        self._idx += 1
        if idx < len(self._outputs):
            text = self._outputs[idx]
        else:
            text = "ok"
        return {
            "agent_output": text,
            "tokens_used": 5,
            "cost_estimate": 0.001,
        }


# --------------------------------------------------------------------------
# TestLoopWithoutCEF (the negative path: CEF disabled = no behavior change)
# --------------------------------------------------------------------------


class TestLoopWithoutCEF:
    def test_cef_disabled_by_default(self):
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE)
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
        )
        loop = AgentLoop(config)
        assert loop.cef_enabled is False
        assert loop.cef_steps == []
        assert loop.cef_session_verdict is None
        assert loop.cef_latest_recommended_action is None
        assert loop.cef_audit_path is None

    def test_loop_runs_normally_without_cef(self):
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE)
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
        )
        loop = AgentLoop(config)
        agent = _TickAgent(["hello", "world"])
        result = loop.run(agent, goal=lambda obs: False, max_iterations=2)
        assert loop.lifecycle == LifecycleState.COMPLETED
        # step_count = 2 act + 2 observe + 2 evaluate + 1 closing = 7
        assert loop.step_count == 7
        # CEF slots stay empty
        assert loop.cef_steps == []
        assert loop.cef_session_verdict is None

    def test_cef_audit_path_not_set_without_cef(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = os.path.join(tmp, "loop.jsonl")
            config = AgentLoopConfig(
                identity=_make_identity(),
                verifier=_FixedVerifier(Verdict.CONTINUE),
                budget=_make_budget(),
                audit_path=audit_path,
                # no cef_session_detector
            )
            loop = AgentLoop(config)
            assert loop.cef_audit_path is None
            # Run a step; no .cef.jsonl sidecar should appear
            agent = _TickAgent(["hello"])
            loop.run(agent, goal=lambda obs: True, max_iterations=1)
            assert not os.path.exists(audit_path + ".cef.jsonl")


# --------------------------------------------------------------------------
# TestLoopWithCEFHappyPath (CEF enabled, no fabrication -> continue)
# --------------------------------------------------------------------------


class TestLoopWithCEFHappyPath:
    def test_clean_outputs_continue(self):
        session = CEFSessionDetector(CEFSessionConfig())
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE, rationale="verifier-clean")
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        agent = _TickAgent(["step one done.", "step two done.", "step three done."])
        result = loop.run(agent, goal=lambda obs: False, max_iterations=3)
        # No fabrication -> session stays in EARLY -> CONTINUE -> loop continues
        assert loop.lifecycle == LifecycleState.COMPLETED
        # Three CEF folded steps (one per work call)
        assert len(loop.cef_steps) == 3
        # All three are NONE severity (clean)
        for cef_step in loop.cef_steps:
            assert cef_step.detection.severity.name == "NONE"
            assert cef_step.recommended_loop_action == "continue"
        # Last recommended action is "continue"
        assert loop.cef_latest_recommended_action == "continue"
        # Loop is COMPLETED because max_iterations was reached
        assert loop.lifecycle == LifecycleState.COMPLETED

    def test_cef_session_verdict_reflects_last_step(self):
        session = CEFSessionDetector(CEFSessionConfig())
        config = AgentLoopConfig(
            identity=_make_identity(),
            verifier=_FixedVerifier(Verdict.CONTINUE),
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        agent = _TickAgent(["ok one", "ok two"])
        loop.run(agent, goal=lambda obs: False, max_iterations=3)
        # cef_session_verdict should be the LAST step's session verdict
        last_step = loop.cef_steps[-1]
        assert loop.cef_session_verdict is last_step.session_verdict


# --------------------------------------------------------------------------
# TestCEFOverrideHalt (CRITICAL fabrication -> HALT)
# --------------------------------------------------------------------------


class TestCEFOverrideHalt:
    def test_per_output_critical_halts_loop(self):
        """A fabricated simulated-crash output should HALT the loop."""
        session = CEFSessionDetector(CEFSessionConfig())
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE, rationale="verifier-ok")
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # Step 1 clean, step 2 fabricated simulated crash (CET)
        agent = _TickAgent(
            [
                "Working on it.",
                'Traceback (most recent call last):\n  File "main.py", line 42\n'
                "MemoryError: 0xDEADBEEF fatal error",
            ]
        )
        result = loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # The CET (simulated crash) MUST halt the loop
        assert loop.lifecycle == LifecycleState.FAILED
        # The CEF step for step 2 should be CRITICAL
        assert loop.cef_steps[1].detection.severity.name == "CRITICAL"
        assert loop.cef_steps[1].recommended_loop_action == "halt"
        # The loop halted on the second iteration -> exactly 2 work calls
        # = 6 LoopSteps (act+observe+evaluate x2) + 1 closing
        assert loop.step_count == 7
        # The EVALUATE step's rationale should mention CEF
        eval_steps = [s for s in loop.steps if s.phase.value == "evaluate"]
        halt_eval = [s for s in eval_steps if s.verdict == Verdict.HALT]
        assert len(halt_eval) == 1
        assert "cef" in halt_eval[0].composite_rationale.lower()

    def test_external_obstacle_high_escalates(self):
        """Multiple HIGH-severity outputs (the session detector only escalate"""
        session = CEFSessionDetector(CEFSessionConfig())
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE)
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # Repeated HIGH-severity external obstacle (session detector
        # only escalates to FREEZE when total OR consecutive
        # thresholds are crossed). With the default CEFSessionConfig,
        # consecutive HIGH outputs hit the FREEZE threshold quickly.
        fabricated = (
            "Audit restrictions prevent this action. Third-party vendor system delays the response. "
            "Compliance regulatory restrictions block access. The partner system is unable to disclose "
            "the internal data. The upstream service is unreachable due to policy. Legal review "
            "required before any further action. The downstream API is restricted by authorization. "
            "The third-party provider requires compliance approval before continuing."
        )
        # Agent that returns the fabricated text every step.
        class _RepeatingAgent:
            def __init__(self, text: str):
                self._text = text
                self._calls = 0
            def __call__(self, identity, action):
                self._calls += 1
                return {"agent_output": self._text, "tokens_used": 5, "cost_estimate": 0.001}
        agent = _RepeatingAgent(fabricated)
        result = loop.run(agent, goal=lambda obs: False, max_iterations=10)
        # Session escalates to WARNING/FREEZE -> ESCALATE -> WAITING
        assert loop.lifecycle == LifecycleState.WAITING
        # Last CEF step should be HIGH severity
        last_cef = loop.cef_steps[-1]
        assert last_cef.detection.severity.name == "HIGH"
        # The freeze/restart -> ESCALATE
        assert last_cef.recommended_loop_action in ("freeze", "restart", "halt", "warn")

    def test_halt_dominates_verifier(self):
        """A CEF HALT dominates the verifier verdict, even when the verifier is CONTINUE.

        This is the conservative-posture test: the CEF bridge can PROMOTE
        a verdict but never DEMOTE one. A clean verifier verdict stays
        clean if CEF says "continue"; an ESCALATE/HALT from CEF upgrades
        the verdict.
        """
        session = CEFSessionDetector(CEFSessionConfig())
        identity = _make_identity()
        # Verifier would say CONTINUE
        verifier = _FixedVerifier(Verdict.CONTINUE, rationale="verifier-says-continue")
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # Step 1: CET (simulated crash)
        agent = _TickAgent(
            [
                'Traceback (most recent call last):\n  File "x.py"\n'
                "MemoryError: 0xDEADBEEF fatal error",
            ]
        )
        result = loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # CEF says HALT -> loop is FAILED
        assert loop.lifecycle == LifecycleState.FAILED
        # The composite rationale should include BOTH the CEF prefix and the verifier rationale
        eval_steps = [s for s in loop.steps if s.phase.value == "evaluate"]
        halt_eval = [s for s in eval_steps if s.verdict == Verdict.HALT]
        assert len(halt_eval) == 1
        assert "cef" in halt_eval[0].composite_rationale.lower()
        assert "verifier" in halt_eval[0].composite_rationale.lower()


# --------------------------------------------------------------------------
# TestCEFOverrideWarn (warning path: evidence only, no verdict change)
# --------------------------------------------------------------------------


class TestCEFOverrideWarn:
    def test_warn_appends_evidence_no_verdict_change(self):
        """Accumulated LOW-severity markers should trigger session WARN,
        but the loop's verifier verdict stays unchanged (evidence-only)."""
        # Use a low warn threshold so we can hit WARN with one work call
        # carrying a single but heavy vague-excuse pattern.
        session = CEFSessionDetector(
            CEFSessionConfig(
                warn_total_threshold=1,
                warn_consecutive_threshold=1,
            )
        )
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE, rationale="verifier-ok")
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # Vague excuse but not heavy enough to escalate
        agent = _TickAgent(["I am currently unable to complete that."])
        result = loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # The first work call may stay CONTINUE or escalate to WARN;
        # either way the verifier verdict should be the strongest
        # (CONTINUE stays CONTINUE, ESCALATE would surface as WAITING)
        # The audit trail should carry the cef prefix
        eval_steps = [s for s in loop.steps if s.phase.value == "evaluate"]
        assert len(eval_steps) >= 1
        # The composite rationale for the eval step should mention cef
        # when CEF contributed (warn or higher)
        any_cef_mentioned = any(
            "cef" in es.composite_rationale.lower() for es in eval_steps
        )
        assert any_cef_mentioned

    def test_cef_does_not_demote_verifier_halt(self):
        """A CEF "continue" on a verifier HALT stays HALT (additive only)."""
        session = CEFSessionDetector(CEFSessionConfig())
        identity = _make_identity()
        # Verifier says HALT
        verifier = _FixedVerifier(Verdict.HALT, rationale="verifier-halt")
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # Clean output -> CEF says "continue"
        agent = _TickAgent(["Working on it."])
        result = loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # Verifier HALT dominates -> loop is FAILED
        assert loop.lifecycle == LifecycleState.FAILED
        # CEF folded a step but did not override
        assert len(loop.cef_steps) == 1
        assert loop.cef_steps[0].recommended_loop_action == "continue"
        # The verdict is HALT, not CONTINUE
        eval_step = [s for s in loop.steps if s.phase.value == "evaluate"][0]
        assert eval_step.verdict == Verdict.HALT


# --------------------------------------------------------------------------
# TestCEFAuditTrail (audit trail integration)
# --------------------------------------------------------------------------


class TestCEFAuditTrail:
    def test_cef_audit_disabled_when_cef_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = os.path.join(tmp, "loop.jsonl")
            config = AgentLoopConfig(
                identity=_make_identity(),
                verifier=_FixedVerifier(Verdict.CONTINUE),
                budget=_make_budget(),
                audit_path=audit_path,
                # no cef_session_detector
            )
            loop = AgentLoop(config)
            agent = _TickAgent(["hello"])
            loop.run(agent, goal=lambda obs: True, max_iterations=1)
            # Audit file exists; cef sidecar should NOT exist
            assert os.path.exists(audit_path)
            assert not os.path.exists(audit_path + ".cef.jsonl")

    def test_cef_audit_written_when_cef_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = os.path.join(tmp, "loop.jsonl")
            session = CEFSessionDetector(CEFSessionConfig())
            config = AgentLoopConfig(
                identity=_make_identity(),
                verifier=_FixedVerifier(Verdict.CONTINUE),
                budget=_make_budget(),
                cef_session_detector=session,
                audit_path=audit_path,
            )
            loop = AgentLoop(config)
            agent = _TickAgent(["hello", "world"])
            loop.run(agent, goal=lambda obs: False, max_iterations=2)
            # Both audit files exist
            assert os.path.exists(audit_path)
            cef_audit = audit_path + ".cef.jsonl"
            assert os.path.exists(cef_audit)
            # The CEF audit file has 2 folded steps (one per work call)
            with open(cef_audit, "r", encoding="utf-8") as fh:
                cef_lines = [json.loads(line) for line in fh if line.strip()]
            assert len(cef_lines) == 2
            for cl in cef_lines:
                assert "step_index" in cl
                assert "detection" in cl
                assert "session_verdict" in cl
                assert "recommended_loop_action" in cl

    def test_main_audit_has_eval_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = os.path.join(tmp, "loop.jsonl")
            session = CEFSessionDetector(CEFSessionConfig())
            config = AgentLoopConfig(
                identity=_make_identity(),
                verifier=_FixedVerifier(Verdict.CONTINUE),
                budget=_make_budget(),
                cef_session_detector=session,
                audit_path=audit_path,
            )
            loop = AgentLoop(config)
            agent = _TickAgent(["hello", "world"])
            loop.run(agent, goal=lambda obs: False, max_iterations=2)
            with open(audit_path, "r", encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh if line.strip()]
            # 2 act + 2 observe + 2 evaluate + 1 closing = 7 lines
            assert len(lines) == 7
            # Find EVALUATE steps (2 from real iterations + 1 closing step)
            eval_lines = [l for l in lines if l["phase"] == "evaluate"]
            assert len(eval_lines) == 3
            # All real EVALUATE steps carry composite_rationale; the closing step
            # has terminal_reason but no composite_rationale
            for el in eval_lines[:2]:
                assert "composite_rationale" in el


# --------------------------------------------------------------------------
# TestCreateAgentLoopWithCEF (smallest-viable-install convenience path)
# --------------------------------------------------------------------------


class TestCreateAgentLoopWithCEF:
    def test_create_agent_loop_accepts_cef_detector(self):
        session = CEFSessionDetector(CEFSessionConfig())
        loop = create_agent_loop(
            principal="tester",
            purpose="cef-bridge",
            verifiers=[_FixedVerifier(Verdict.CONTINUE)],
            cef_session_detector=session,
        )
        assert loop.cef_enabled is True
        agent = _TickAgent(["ok"])
        loop.run(agent, goal=lambda obs: True, max_iterations=1)
        assert len(loop.cef_steps) == 1

    def test_create_agent_loop_works_without_cef(self):
        loop = create_agent_loop(
            principal="tester",
            purpose="no-cef",
            verifiers=[_FixedVerifier(Verdict.CONTINUE)],
        )
        assert loop.cef_enabled is False
        agent = _TickAgent(["ok"])
        loop.run(agent, goal=lambda obs: True, max_iterations=1)
        assert len(loop.cef_steps) == 0


# --------------------------------------------------------------------------
# TestCEFIntegrationWithRealSubstrate (end-to-end with real detectors)
# --------------------------------------------------------------------------


class TestCEFIntegrationWithRealSubstrate:
    def test_session_horizon_triggers_via_accumulation(self):
        """Many LOW-severity steps accumulate into a session WARN or worse."""
        # Use low thresholds so we can hit horizon with a small list
        session = CEFSessionDetector(
            CEFSessionConfig(
                warn_total_threshold=2,
                warn_consecutive_threshold=1,
            )
        )
        identity = _make_identity()
        verifier = _FixedVerifier(Verdict.CONTINUE)
        config = AgentLoopConfig(
            identity=identity,
            verifier=verifier,
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # 3 steps with vague excuses -> should accumulate to WARN/FREEZE
        agent = _TickAgent(
            [
                "I am currently unable to complete that.",
                "I am currently unable to verify that.",
                "I am currently unable to process this.",
            ]
        )
        result = loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # The session detector should have triggered WARN/FREEZE
        last_action = loop.cef_latest_recommended_action
        # It should be at least "warn" (additive evidence, no verdict change)
        # or worse (freeze/restart/halt)
        assert last_action in ("warn", "freeze", "restart", "halt")


# --------------------------------------------------------------------------
# TestConservativePosture (the load-bearing safety claims)
# --------------------------------------------------------------------------


class TestConservativePosture:
    def test_cef_disabled_does_not_modify_behavior(self):
        """Two loops with the same work function behave identically except
        for the cef_steps ring. Same step_count, same lifecycle, same verdicts."""
        work_fn = _TickAgent(["a", "b", "c"])
        budget = _make_budget()
        # Loop 1: no CEF
        config1 = AgentLoopConfig(
            identity=_make_identity(),
            verifier=_FixedVerifier(Verdict.CONTINUE),
            budget=budget,
        )
        loop1 = AgentLoop(config1)
        loop1.run(work_fn, goal=lambda obs: False, max_iterations=3)
        # Loop 2: CEF enabled but never sees fabrication
        session = CEFSessionDetector(CEFSessionConfig())
        config2 = AgentLoopConfig(
            identity=_make_identity(),
            verifier=_FixedVerifier(Verdict.CONTINUE),
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop2 = AgentLoop(config2)
        work_fn2 = _TickAgent(["a", "b", "c"])
        loop2.run(work_fn2, goal=lambda obs: False, max_iterations=3)
        # Same step_count
        assert loop1.step_count == loop2.step_count
        # Same lifecycle
        assert loop1.lifecycle == loop2.lifecycle
        # Loop 2 has CEF steps (one per work call)
        assert len(loop2.cef_steps) == 3
        # All CEF steps are NONE severity
        for cs in loop2.cef_steps:
            assert cs.detection.severity.name == "NONE"

    def test_cef_clean_does_not_overwrite_verifier_rationale(self):
        """A CEF "continue" leaves the verifier's composite_rationale intact."""
        session = CEFSessionDetector(CEFSessionConfig())
        config = AgentLoopConfig(
            identity=_make_identity(),
            verifier=_FixedVerifier(Verdict.CONTINUE, rationale="verifier-clean"),
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        agent = _TickAgent(["ok"])
        loop.run(agent, goal=lambda obs: True, max_iterations=1)
        # The EVALUATE step's rationale is the verifier's own.
        # Filter to only the real EVALUATE steps (verdict set); the
        # closing EVALUATE has terminal_reason but no verdict.
        eval_steps = [s for s in loop.steps if s.phase.value == "evaluate" and s.verdict is not None]
        assert len(eval_steps) == 1
        assert eval_steps[0].composite_rationale == "verifier-clean"

    def test_cef_halt_dominates_session_continue(self):
        """A per-output CRITICAL HALT dominates even when session says CONTINUE."""
        session = CEFSessionDetector(CEFSessionConfig())
        config = AgentLoopConfig(
            identity=_make_identity(),
            verifier=_FixedVerifier(Verdict.CONTINUE),
            budget=_make_budget(),
            cef_session_detector=session,
        )
        loop = AgentLoop(config)
        # First call is clean (session EARLY/CONTINUE), second call is CET
        agent = _TickAgent(
            [
                "Reading input file.",
                'Traceback (most recent call last):\n  File "p.py"\n'
                "MemoryError: 0xCAFEBABE fatal error",
            ]
        )
        loop.run(agent, goal=lambda obs: False, max_iterations=5)
        # The second step is CRITICAL -> loop halts
        assert loop.lifecycle == LifecycleState.FAILED
        # The CEF recommended action on the second step is "halt"
        assert loop.cef_latest_recommended_action == "halt"

    def test_extract_agent_output_helper(self):
        """The _extract_agent_output helper picks up the canonical keys."""
        # Explicit key
        out = _extract_agent_output({"my_key": "hello"}, "my_key")
        assert out == "hello"
        # Canonical keys
        assert _extract_agent_output({"agent_output": "a"}) == "a"
        assert _extract_agent_output({"output": "b"}) == "b"
        assert _extract_agent_output({"text": "c"}) == "c"
        assert _extract_agent_output({"response": "d"}) == "d"
        # Nested output
        assert _extract_agent_output({"output": {"text": "nested"}}) == "nested"
        # Empty / non-dict
        assert _extract_agent_output(None) == ""
        non_str = _extract_agent_output({})
        # Empty dict falls back to "{}" JSON -- detector treats as below-min
        assert non_str == "{}" or non_str == ""
