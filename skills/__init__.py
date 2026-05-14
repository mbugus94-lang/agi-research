"""
Skills module for AGI agents.
Provides modular capabilities that can be registered with the agent.
"""

from .web_search import (
    WebSearchSkill,
    SearchResult,
    web_search,
    deep_research,
    summarize_search
)

from .code_gen import (
    CodeGenSkill,
    CodeResult,
    CodeAction,
    generate_code,
    propose_modification,
    review_code
)

from .analysis import (
    AnalysisSkill,
    AnalysisResult,
    analyze_patterns,
    analyze_trends,
    synthesize,
    generate_hypothesis
)

from .skill_acquisition import (
    Skill,
    SkillStatus,
    SkillType,
    SkillDemonstration,
    ExecutionStep,
    SkillCrystallizer,
    create_crystallizer,
    quick_crystallize
)

__all__ = [
    # Web Search
    "WebSearchSkill",
    "SearchResult",
    "web_search",
    "deep_research",
    "summarize_search",
    
    # Code Generation
    "CodeGenSkill",
    "CodeResult",
    "CodeAction",
    "generate_code",
    "propose_modification",
    "review_code",
    
    # Analysis
    "AnalysisSkill",
    "AnalysisResult",
    "analyze_patterns",
    "analyze_trends",
    "synthesize",
    "generate_hypothesis",
    
    # Skill Acquisition (Self-Evolving)
    "Skill",
    "SkillStatus",
    "SkillType",
    "SkillDemonstration",
    "ExecutionStep",
    "SkillCrystallizer",
    "create_crystallizer",
    "quick_crystallize"
]
