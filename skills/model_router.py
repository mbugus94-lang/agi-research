"""
Multi-Model Router Skill

Implements intelligent routing across multiple LLM providers based on:
- Task characteristics (multimodal, coding, reasoning, etc.)
- Cost constraints and performance requirements
- Model capabilities and availability

Based on 2026 research showing 85% cost reduction with intelligent routing:
- 70% to cost-optimized models (Flash, Mini)
- 25% to mid-tier models (Sonnet, Pro)
- 5% to frontier models (Opus, GPT-5.5)

Key References:
- AI.cc multi-model routing architecture
- Datadog State of AI Engineering 2026
- LangGraph state management patterns
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum, auto
from collections import defaultdict
import time
import json


class TaskType(Enum):
    """Categories of tasks for routing decisions."""
    CODE_GENERATION = auto()
    CODE_REVIEW = auto()
    MULTIMODAL = auto()
    REASONING = auto()
    SUMMARIZATION = auto()
    CREATIVE_WRITING = auto()
    DATA_ANALYSIS = auto()
    LONG_CONTEXT = auto()
    TOOL_USE = auto()
    CHAT = auto()


class ModelTier(Enum):
    """Model capability tiers."""
    FRONTIER = "frontier"      # Most capable, most expensive
    PREMIUM = "premium"        # High capability, moderate cost
    STANDARD = "standard"      # Balanced capability/cost
    ECONOMY = "economy"        # Cost-optimized for simple tasks


@dataclass
class ModelCapability:
    """Capabilities and characteristics of a model."""
    model_id: str
    provider: str
    tier: ModelTier
    
    # Task suitability scores (0.0-1.0)
    task_scores: Dict[TaskType, float] = field(default_factory=dict)
    
    # Performance characteristics
    context_window: int = 128000
    supports_vision: bool = False
    supports_tools: bool = True
    supports_json_mode: bool = True
    
    # Cost per 1M tokens (input, output)
    cost_per_1m_tokens: Tuple[float, float] = (5.0, 15.0)
    
    # Latency characteristics (typical TTFT in ms)
    typical_latency_ms: float = 500.0
    
    # Reliability metrics
    rate_limit_rpm: int = 60
    success_rate_24h: float = 0.99
    
    def get_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        input_cost = (input_tokens / 1_000_000) * self.cost_per_1m_tokens[0]
        output_cost = (output_tokens / 1_000_000) * self.cost_per_1m_tokens[1]
        return input_cost + output_cost


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    model_id: str
    provider: str
    task_type: TaskType
    confidence: float
    reason: str
    estimated_cost: float
    estimated_latency_ms: float
    alternatives: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "task_type": self.task_type.name,
            "confidence": self.confidence,
            "reason": self.reason,
            "estimated_cost": self.estimated_cost,
            "estimated_latency_ms": self.estimated_latency_ms,
            "alternatives": self.alternatives
        }


@dataclass
class RoutingMetrics:
    """Metrics for routing performance."""
    total_requests: int = 0
    requests_by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requests_by_tier: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    fallback_count: int = 0
    error_count: int = 0
    
    def record_request(self, model_id: str, tier: ModelTier, 
                      cost: float, latency_ms: float, success: bool):
        """Record a request metric."""
        self.total_requests += 1
        self.requests_by_model[model_id] += 1
        self.requests_by_tier[tier.value] += 1
        self.total_cost += cost
        self.total_latency_ms += latency_ms
        if not success:
            self.error_count += 1
    
    def get_average_cost(self) -> float:
        """Get average cost per request."""
        return self.total_cost / max(1, self.total_requests)
    
    def get_average_latency_ms(self) -> float:
        """Get average latency per request."""
        return self.total_latency_ms / max(1, self.total_requests)


class TaskClassifier:
    """Classify tasks for routing decisions."""
    
    # Keywords that indicate task types
    KEYWORDS = {
        TaskType.CODE_GENERATION: [
            "code", "function", "implement", "write code", "generate code",
            "script", "program", "class", "method", "api"
        ],
        TaskType.CODE_REVIEW: [
            "review", "refactor", "optimize", "improve code", "debug",
            "fix", "analyze code", "code review"
        ],
        TaskType.MULTIMODAL: [
            "image", "picture", "photo", "diagram", "chart", "visual",
            "analyze image", "describe image", "vision"
        ],
        TaskType.REASONING: [
            "reason", "logic", "deduce", "infer", "analyze", "solve",
            "puzzle", "math", "calculation", "complex problem"
        ],
        TaskType.SUMMARIZATION: [
            "summarize", "summary", "tl;dr", "condense", "brief",
            "overview", "key points", "main ideas"
        ],
        TaskType.CREATIVE_WRITING: [
            "write", "story", "creative", "poem", "blog", "essay",
            "draft", "compose", "narrative"
        ],
        TaskType.DATA_ANALYSIS: [
            "analyze data", "statistics", "correlation", "trend",
            "dataset", "csv", "table", "numbers"
        ],
        TaskType.LONG_CONTEXT: [
            "long document", "book", "paper", "article", "report",
            "large context", "many pages", "extensive"
        ],
        TaskType.TOOL_USE: [
            "tool", "function call", "api call", "search", "fetch",
            "retrieve", "database", "external data"
        ]
    }
    
    @classmethod
    def classify(cls, prompt: str, context: Optional[Dict] = None) -> TaskType:
        """Classify a task based on prompt content."""
        prompt_lower = prompt.lower()
        scores = {}
        
        for task_type, keywords in cls.KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[task_type] = score
        
        # Check context hints
        if context:
            if context.get("has_images"):
                scores[TaskType.MULTIMODAL] = scores.get(TaskType.MULTIMODAL, 0) + 3
            if context.get("requires_tools"):
                scores[TaskType.TOOL_USE] = scores.get(TaskType.TOOL_USE, 0) + 3
            if context.get("context_length", 0) > 100000:
                scores[TaskType.LONG_CONTEXT] = scores.get(TaskType.LONG_CONTEXT, 0) + 3
        
        if not scores:
            return TaskType.CHAT
        
        return max(scores, key=scores.get)


class ModelRouter:
    """
    Intelligent model router for multi-LLM systems.
    
    Implements cost-aware routing with quality guarantees:
    - Route simple tasks to economy models
    - Route complex tasks to appropriate premium/frontier models
    - Track performance and adjust routing over time
    """
    
    # Default model registry with 2026-era models
    DEFAULT_MODELS = {
        # Frontier models - highest capability
        "gpt-5.5": ModelCapability(
            model_id="gpt-5.5",
            provider="openai",
            tier=ModelTier.FRONTIER,
            task_scores={
                TaskType.CODE_GENERATION: 0.95,
                TaskType.REASONING: 0.95,
                TaskType.TOOL_USE: 0.98,
                TaskType.MULTIMODAL: 0.90,
                TaskType.LONG_CONTEXT: 0.95
            },
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1m_tokens=(15.0, 60.0),
            typical_latency_ms=800
        ),
        "claude-opus-4.7": ModelCapability(
            model_id="claude-opus-4.7",
            provider="anthropic",
            tier=ModelTier.FRONTIER,
            task_scores={
                TaskType.CODE_GENERATION: 0.97,
                TaskType.CODE_REVIEW: 0.95,
                TaskType.REASONING: 0.96,
                TaskType.CREATIVE_WRITING: 0.95,
                TaskType.LONG_CONTEXT: 0.98
            },
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1m_tokens=(15.0, 75.0),
            typical_latency_ms=900
        ),
        
        # Premium models - high capability, better cost
        "claude-sonnet-4.6": ModelCapability(
            model_id="claude-sonnet-4.6",
            provider="anthropic",
            tier=ModelTier.PREMIUM,
            task_scores={
                TaskType.CODE_GENERATION: 0.90,
                TaskType.CODE_REVIEW: 0.92,
                TaskType.REASONING: 0.88,
                TaskType.CREATIVE_WRITING: 0.88,
                TaskType.SUMMARIZATION: 0.92
            },
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1m_tokens=(3.0, 15.0),
            typical_latency_ms=400
        ),
        "gemini-3.1-pro": ModelCapability(
            model_id="gemini-3.1-pro",
            provider="google",
            tier=ModelTier.PREMIUM,
            task_scores={
                TaskType.MULTIMODAL: 0.95,
                TaskType.REASONING: 0.85,
                TaskType.LONG_CONTEXT: 0.92,
                TaskType.DATA_ANALYSIS: 0.88
            },
            context_window=1000000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1m_tokens=(3.5, 10.5),
            typical_latency_ms=350
        ),
        "deepseek-v4": ModelCapability(
            model_id="deepseek-v4",
            provider="deepseek",
            tier=ModelTier.PREMIUM,
            task_scores={
                TaskType.CODE_GENERATION: 0.92,
                TaskType.REASONING: 0.90,
                TaskType.CODE_REVIEW: 0.88
            },
            context_window=64000,
            supports_vision=False,
            supports_tools=True,
            cost_per_1m_tokens=(0.5, 2.0),
            typical_latency_ms=600
        ),
        
        # Standard models - balanced capability/cost
        "gpt-4.1": ModelCapability(
            model_id="gpt-4.1",
            provider="openai",
            tier=ModelTier.STANDARD,
            task_scores={
                TaskType.CHAT: 0.90,
                TaskType.SUMMARIZATION: 0.88,
                TaskType.TOOL_USE: 0.85,
                TaskType.REASONING: 0.82
            },
            context_window=128000,
            supports_vision=False,
            supports_tools=True,
            cost_per_1m_tokens=(2.5, 10.0),
            typical_latency_ms=300
        ),
        "llama-4-scout": ModelCapability(
            model_id="llama-4-scout",
            provider="meta",
            tier=ModelTier.STANDARD,
            task_scores={
                TaskType.LONG_CONTEXT: 0.90,
                TaskType.SUMMARIZATION: 0.85,
                TaskType.CHAT: 0.82
            },
            context_window=128000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1m_tokens=(0.2, 0.6),
            typical_latency_ms=250
        ),
        
        # Economy models - cost-optimized
        "gpt-4.1-mini": ModelCapability(
            model_id="gpt-4.1-mini",
            provider="openai",
            tier=ModelTier.ECONOMY,
            task_scores={
                TaskType.CHAT: 0.80,
                TaskType.SUMMARIZATION: 0.78
            },
            context_window=128000,
            supports_vision=False,
            supports_tools=True,
            cost_per_1m_tokens=(0.15, 0.60),
            typical_latency_ms=150
        ),
        "deepseek-v4-flash": ModelCapability(
            model_id="deepseek-v4-flash",
            provider="deepseek",
            tier=ModelTier.ECONOMY,
            task_scores={
                TaskType.CHAT: 0.75,
                TaskType.SUMMARIZATION: 0.75,
                TaskType.CODE_GENERATION: 0.78
            },
            context_window=64000,
            supports_vision=False,
            supports_tools=True,
            cost_per_1m_tokens=(0.1, 0.4),
            typical_latency_ms=100
        )
    }
    
    def __init__(self, 
                 cost_budget: Optional[float] = None,
                 min_quality_threshold: float = 0.75,
                 track_metrics: bool = True):
        """
        Initialize the model router.
        
        Args:
            cost_budget: Maximum cost per request (None for no limit)
            min_quality_threshold: Minimum quality score (0.0-1.0)
            track_metrics: Whether to track routing metrics
        """
        self.models: Dict[str, ModelCapability] = dict(self.DEFAULT_MODELS)
        self.cost_budget = cost_budget
        self.min_quality_threshold = min_quality_threshold
        self.track_metrics = track_metrics
        
        self.metrics = RoutingMetrics() if track_metrics else None
        
        # Routing history for learning
        self.routing_history: List[Dict] = []
        
        # Model availability (can be updated for outages)
        self.available_models: set = set(self.models.keys())
    
    def register_model(self, model: ModelCapability) -> None:
        """Register a new model."""
        self.models[model.model_id] = model
        self.available_models.add(model.model_id)
    
    def set_model_availability(self, model_id: str, available: bool) -> None:
        """Set model availability (for handling outages)."""
        if available:
            self.available_models.add(model_id)
        else:
            self.available_models.discard(model_id)
    
    def route(self, 
              prompt: str, 
              context: Optional[Dict] = None,
              preferred_tier: Optional[ModelTier] = None,
              force_model: Optional[str] = None) -> RoutingDecision:
        """
        Route a request to the best model.
        
        Args:
            prompt: The user prompt
            context: Additional context (has_images, requires_tools, etc.)
            preferred_tier: Prefer models from this tier
            force_model: Force use of specific model
        
        Returns:
            RoutingDecision with selected model and metadata
        """
        # Force specific model if requested
        if force_model and force_model in self.available_models:
            model = self.models[force_model]
            task_type = TaskClassifier.classify(prompt, context)
            return self._create_decision(model, task_type, 1.0, "Forced model selection")
        
        # Classify the task
        task_type = TaskClassifier.classify(prompt, context)
        
        # Score all available models for this task
        candidates = []
        for model_id in self.available_models:
            model = self.models[model_id]
            score = model.task_scores.get(task_type, 0.5)
            
            # Boost score if matches preferred tier
            if preferred_tier and model.tier == preferred_tier:
                score *= 1.2
            
            # Penalize if below quality threshold
            if score < self.min_quality_threshold:
                score *= 0.5
            
            candidates.append((model, score))
        
        # Sort by score
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if not candidates:
            raise ValueError("No available models for routing")
        
        # Apply cost optimization: if top candidate is frontier and budget constrained,
        # check if premium/standard model is good enough
        best_model, best_score = candidates[0]
        
        if self.cost_budget and best_model.tier == ModelTier.FRONTIER:
            for model, score in candidates[1:]:
                if score >= self.min_quality_threshold:
                    est_cost = model.get_cost_estimate(
                        context.get("input_tokens", 1000),
                        context.get("output_tokens", 500)
                    )
                    if est_cost <= self.cost_budget:
                        # Use this cheaper model instead
                        return self._create_decision(
                            model, task_type, score,
                            f"Cost-optimized: {best_model.model_id} score={best_score:.2f}, "
                            f"selected score={score:.2f}, savings={(best_model.cost_per_1m_tokens[0] - model.cost_per_1m_tokens[0]):.2f}x",
                            alternatives=[best_model.model_id]
                        )
        
        # Return top candidate
        alternatives = [m.model_id for m, _ in candidates[1:3]]
        return self._create_decision(
            best_model, task_type, best_score,
            f"Best match for {task_type.name}: score={best_score:.2f}",
            alternatives=alternatives
        )
    
    def _create_decision(self, 
                        model: ModelCapability, 
                        task_type: TaskType,
                        confidence: float,
                        reason: str,
                        alternatives: Optional[List[str]] = None) -> RoutingDecision:
        """Create a routing decision."""
        return RoutingDecision(
            model_id=model.model_id,
            provider=model.provider,
            task_type=task_type,
            confidence=confidence,
            reason=reason,
            estimated_cost=model.cost_per_1m_tokens[0] / 1000,  # per 1K tokens
            estimated_latency_ms=model.typical_latency_ms,
            alternatives=alternatives or []
        )
    
    def record_result(self, 
                     decision: RoutingDecision,
                     actual_cost: float,
                     actual_latency_ms: float,
                     success: bool) -> None:
        """Record the result of a routing decision for learning."""
        if self.metrics:
            model = self.models.get(decision.model_id)
            if model:
                self.metrics.record_request(
                    decision.model_id, model.tier,
                    actual_cost, actual_latency_ms, success
                )
        
        self.routing_history.append({
            "decision": decision.to_dict(),
            "actual_cost": actual_cost,
            "actual_latency_ms": actual_latency_ms,
            "success": success,
            "timestamp": time.time()
        })
    
    def get_metrics(self) -> Optional[Dict]:
        """Get routing metrics."""
        if not self.metrics:
            return None
        
        return {
            "total_requests": self.metrics.total_requests,
            "requests_by_model": dict(self.metrics.requests_by_model),
            "requests_by_tier": dict(self.metrics.requests_by_tier),
            "total_cost": self.metrics.total_cost,
            "average_cost": self.metrics.get_average_cost(),
            "average_latency_ms": self.metrics.get_average_latency_ms(),
            "error_rate": self.metrics.error_count / max(1, self.metrics.total_requests)
        }
    
    def get_routing_report(self) -> str:
        """Generate a routing report."""
        if not self.metrics:
            return "Metrics tracking disabled"
        
        lines = ["# Model Routing Report", ""]
        
        lines.append(f"**Total Requests**: {self.metrics.total_requests}")
        lines.append(f"**Total Cost**: ${self.metrics.total_cost:.4f}")
        lines.append(f"**Average Cost**: ${self.metrics.get_average_cost():.4f}/request")
        lines.append(f"**Average Latency**: {self.metrics.get_average_latency_ms():.0f}ms")
        lines.append(f"**Error Rate**: {self.metrics.error_count / max(1, self.metrics.total_requests):.1%}")
        lines.append("")
        
        lines.append("## Requests by Tier")
        for tier, count in sorted(self.metrics.requests_by_tier.items()):
            pct = count / max(1, self.metrics.total_requests) * 100
            lines.append(f"- {tier}: {count} ({pct:.1f}%)")
        lines.append("")
        
        lines.append("## Requests by Model")
        for model, count in sorted(self.metrics.requests_by_model.items(), 
                                   key=lambda x: x[1], reverse=True):
            pct = count / max(1, self.metrics.total_requests) * 100
            lines.append(f"- {model}: {count} ({pct:.1f}%)")
        
        return "\n".join(lines)


# Convenience functions for common routing patterns

def create_default_router(cost_budget: Optional[float] = None) -> ModelRouter:
    """Create a router with default 2026-era models."""
    return ModelRouter(cost_budget=cost_budget)


def route_for_task(prompt: str, 
                  task_type: Optional[TaskType] = None,
                  context: Optional[Dict] = None) -> RoutingDecision:
    """Quick route function using default router."""
    router = create_default_router()
    return router.route(prompt, context)


def get_recommended_model(prompt: str, 
                         context: Optional[Dict] = None) -> str:
    """Get just the recommended model ID."""
    decision = route_for_task(prompt, context=context)
    return decision.model_id


# Example usage patterns

EXAMPLES = """
# Example 1: Basic routing
from skills.model_router import route_for_task

decision = route_for_task("Write a Python function to sort a list")
print(decision.model_id)  # e.g., "deepseek-v4"
print(decision.reason)    # Cost-effective for code generation

# Example 2: With context
from skills.model_router import ModelRouter, TaskType

router = ModelRouter(cost_budget=0.01)
decision = router.route(
    "Analyze this image and describe what you see",
    context={"has_images": True, "input_tokens": 2000}
)
print(decision.model_id)  # "gemini-3.1-pro" or "claude-opus-4.7"

# Example 3: Track metrics
router = ModelRouter(track_metrics=True)
decision = router.route("Summarize this long document")
# ... execute request ...
router.record_result(decision, actual_cost=0.005, actual_latency_ms=400, success=True)
print(router.get_routing_report())
"""
