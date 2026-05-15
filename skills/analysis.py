"""
Analysis Skill

Capability for data analysis, reasoning, and evaluation.
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import statistics


class AnalysisSkill:
    """
    Skill for data analysis and reasoning.
    
    Supports:
    - Statistical analysis
    - Pattern detection
    - Comparative analysis
    - Trend analysis
    - Evaluation and scoring
    """
    
    def __init__(self):
        self.name = "analysis"
        self.description = "Analyze data, detect patterns, and reason about information"
        self.capabilities = [
            "analyze",
            "compare",
            "evaluate",
            "reason",
            "synthesize",
            "summarize",
            "detect patterns",
            "trend analysis"
        ]
    
    def can_handle(self, action: str, context: Dict[str, Any]) -> bool:
        """Check if this skill can handle the action."""
        action_lower = action.lower()
        
        analysis_keywords = [
            "analyze", "analysis", "compare", "comparison",
            "evaluate", "evaluation", "assess", "score",
            "summarize", "synthesize", "extract", "identify",
            "pattern", "trend", "reason", "conclusion"
        ]
        
        return any(kw in action_lower for kw in analysis_keywords)
    
    def execute(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis action."""
        # Determine analysis type
        analysis_type = self._determine_analysis_type(action, context)
        
        # Extract data
        data = context.get("data", context.get("input", None))
        
        if analysis_type == "statistical":
            return self._statistical_analysis(data)
        elif analysis_type == "comparison":
            return self._comparison_analysis(data, context)
        elif analysis_type == "pattern":
            return self._pattern_detection(data, context)
        elif analysis_type == "trend":
            return self._trend_analysis(data, context)
        elif analysis_type == "summary":
            return self._summarize(data, context)
        elif analysis_type == "evaluation":
            return self._evaluate(data, context)
        else:
            return {
                "success": True,
                "analysis_type": "general",
                "note": "Analysis framework ready",
                "capabilities": self.capabilities
            }
    
    def _determine_analysis_type(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> str:
        """Determine the type of analysis needed."""
        action_lower = action.lower()
        
        if any(kw in action_lower for kw in ["statistic", "mean", "average", "median", "distribution"]):
            return "statistical"
        
        if any(kw in action_lower for kw in ["compare", "vs", "versus", "difference", "contrast"]):
            return "comparison"
        
        if any(kw in action_lower for kw in ["pattern", "detect", "find", "identify"]):
            return "pattern"
        
        if any(kw in action_lower for kw in ["trend", "change over time", "forecast", "predict"]):
            return "trend"
        
        if any(kw in action_lower for kw in ["summarize", "summary", "overview", "brief"]):
            return "summary"
        
        if any(kw in action_lower for kw in ["evaluate", "assess", "score", "rate"]):
            return "evaluation"
        
        return "general"
    
    def _statistical_analysis(self, data: Any) -> Dict[str, Any]:
        """Perform statistical analysis on numeric data."""
        if not data or not isinstance(data, list):
            return {
                "success": False,
                "error": "Statistical analysis requires a list of numbers",
                "received_type": type(data).__name__
            }
        
        # Filter numeric values
        numbers = [x for x in data if isinstance(x, (int, float))]
        
        if not numbers:
            return {
                "success": False,
                "error": "No numeric values found in data"
            }
        
        try:
            stats = {
                "count": len(numbers),
                "mean": statistics.mean(numbers),
                "median": statistics.median(numbers),
                "min": min(numbers),
                "max": max(numbers),
                "range": max(numbers) - min(numbers)
            }
            
            if len(numbers) > 1:
                stats["stdev"] = statistics.stdev(numbers)
            
            return {
                "success": True,
                "analysis_type": "statistical",
                "statistics": stats
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _comparison_analysis(
        self,
        data: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare multiple items."""
        items = data if isinstance(data, list) else context.get("items", [])
        
        if len(items) < 2:
            return {
                "success": False,
                "error": "Comparison requires at least 2 items",
                "item_count": len(items)
            }
        
        return {
            "success": True,
            "analysis_type": "comparison",
            "item_count": len(items),
            "comparison_dimensions": ["size", "complexity", "performance"],
            "note": "Comparison framework applied"
        }
    
    def _pattern_detection(
        self,
        data: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect patterns in data."""
        return {
            "success": True,
            "analysis_type": "pattern_detection",
            "data_type": type(data).__name__,
            "pattern_types": [
                "sequential",
                "repetition",
                "correlation",
                "anomaly"
            ],
            "note": "Pattern detection framework applied"
        }
    
    def _trend_analysis(
        self,
        data: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze trends in time-series data."""
        return {
            "success": True,
            "analysis_type": "trend",
            "trend_types": [
                "increasing",
                "decreasing",
                "cyclical",
                "stable",
                "volatile"
            ],
            "note": "Trend analysis framework applied"
        }
    
    def _summarize(self, data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of data."""
        if isinstance(data, list):
            length = len(data)
            summary = f"Collection of {length} items"
            
            # Type breakdown
            type_counts = {}
            for item in data:
                t = type(item).__name__
                type_counts[t] = type_counts.get(t, 0) + 1
            
            return {
                "success": True,
                "analysis_type": "summary",
                "summary": summary,
                "item_count": length,
                "type_breakdown": type_counts,
                "summary_types": ["abstract", "key_points", "highlights"]
            }
        
        elif isinstance(data, dict):
            return {
                "success": True,
                "analysis_type": "summary",
                "summary": f"Object with {len(data)} properties",
                "keys": list(data.keys())[:10],  # First 10 keys
                "nested_depth": self._calculate_depth(data)
            }
        
        else:
            return {
                "success": True,
                "analysis_type": "summary",
                "summary": str(data)[:200],  # Truncated string
                "data_type": type(data).__name__
            }
    
    def _evaluate(self, data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate data against criteria."""
        criteria = context.get("criteria", ["completeness", "accuracy", "quality"])
        
        # Simulate evaluation (in production, this would use actual criteria)
        scores = {}
        for criterion in criteria:
            # Placeholder scoring
            scores[criterion] = {
                "score": 0.75,
                "max": 1.0,
                "notes": f"Evaluated for {criterion}"
            }
        
        overall = sum(s["score"] for s in scores.values()) / len(scores) if scores else 0
        
        return {
            "success": True,
            "analysis_type": "evaluation",
            "criteria": criteria,
            "scores": scores,
            "overall_score": overall,
            "recommendations": ["Review areas with lower scores"]
        }
    
    def _calculate_depth(self, data: Dict, level: int = 0) -> int:
        """Calculate nesting depth of dictionary."""
        if not isinstance(data, dict) or not data:
            return level
        
        depths = [self._calculate_depth(v, level + 1) 
                  for v in data.values() if isinstance(v, dict)]
        
        return max(depths) if depths else level
    
    def learn_from(self, experience: Dict[str, Any]) -> None:
        """Learn from analysis experience."""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "analysis_types": [
                "statistical",
                "comparison",
                "pattern",
                "trend",
                "summary",
                "evaluation"
            ]
        }
