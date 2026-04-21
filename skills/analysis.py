"""
Analysis Skill

Provides AGI agent with analytical capabilities:
- Pattern recognition
- Trend analysis
- Data synthesis
- Hypothesis generation

Based on ARC-AGI research: compositional reasoning is critical.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import Counter
from statistics import mean, median, stdev


@dataclass
class AnalysisResult:
    """Result of an analysis"""
    analysis_type: str
    findings: List[Dict]
    confidence: float
    metadata: Dict
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "analysis_type": self.analysis_type,
            "findings": self.findings,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class AnalysisSkill:
    """
    Analytical capabilities for the AGI agent.
    
    Supports:
    - Pattern analysis
    - Trend detection
    - Comparative analysis
    - Hypothesis testing
    """
    
    def __init__(self):
        self.analysis_history: List[Dict] = []
    
    def analyze_patterns(self, 
                        data: List[Any],
                        pattern_type: str = "frequency") -> AnalysisResult:
        """
        Analyze patterns in data.
        
        Pattern types: frequency, sequence, correlation, anomaly
        """
        findings = []
        
        if pattern_type == "frequency":
            # Frequency analysis
            if all(isinstance(d, (str, int)) for d in data):
                counter = Counter(data)
                most_common = counter.most_common(5)
                findings.append({
                    "type": "frequency",
                    "most_common": most_common,
                    "unique_count": len(counter),
                    "total_count": len(data)
                })
        
        elif pattern_type == "sequence":
            # Sequence analysis (pairs, triplets)
            if len(data) >= 2:
                pairs = list(zip(data[:-1], data[1:]))
                pair_counter = Counter(pairs)
                findings.append({
                    "type": "sequence",
                    "common_pairs": pair_counter.most_common(3),
                    "pattern_strength": len(pair_counter) / len(pairs) if pairs else 0
                })
        
        elif pattern_type == "anomaly":
            # Anomaly detection for numeric data
            numeric = [d for d in data if isinstance(d, (int, float))]
            if numeric:
                avg = mean(numeric)
                std = stdev(numeric) if len(numeric) > 1 else 0
                threshold = avg + (2 * std)
                
                anomalies = [d for d in numeric if abs(d - avg) > 2 * std]
                findings.append({
                    "type": "anomaly",
                    "mean": avg,
                    "std": std,
                    "anomaly_count": len(anomalies),
                    "anomaly_rate": len(anomalies) / len(numeric),
                    "threshold": threshold
                })
        
        return AnalysisResult(
            analysis_type=f"pattern_{pattern_type}",
            findings=findings,
            confidence=0.7 if findings else 0.3,
            metadata={"data_size": len(data)}
        )
    
    def analyze_trends(self,
                      time_series: List[Tuple[str, float]],
                      window_size: int = 3) -> AnalysisResult:
        """
        Analyze trends in time-series data.
        
        Returns trend direction, strength, and predictions.
        """
        if len(time_series) < 2:
            return AnalysisResult(
                analysis_type="trend",
                findings=[{"type": "insufficient_data"}],
                confidence=0.0,
                metadata={"data_points": len(time_series)}
            )
        
        # Extract values
        values = [v for _, v in time_series]
        
        # Calculate trend
        if len(values) >= window_size:
            # Moving average trend
            moving_avgs = []
            for i in range(len(values) - window_size + 1):
                window = values[i:i+window_size]
                moving_avgs.append(mean(window))
            
            trend_direction = "increasing" if moving_avgs[-1] > moving_avgs[0] else "decreasing"
            trend_strength = abs(moving_avgs[-1] - moving_avgs[0]) / (max(values) - min(values) + 0.001)
        else:
            # Simple trend
            trend_direction = "increasing" if values[-1] > values[0] else "decreasing"
            trend_strength = abs(values[-1] - values[0]) / (max(values) - min(values) + 0.001)
        
        # Calculate volatility
        if len(values) > 1:
            volatility = stdev(values) / mean(values) if mean(values) != 0 else 0
        else:
            volatility = 0
        
        findings = [{
            "type": "trend",
            "direction": trend_direction,
            "strength": trend_strength,
            "volatility": volatility,
            "data_points": len(values)
        }]
        
        return AnalysisResult(
            analysis_type="trend",
            findings=findings,
            confidence=min(trend_strength + 0.5, 0.9),
            metadata={"window_size": window_size}
        )
    
    def comparative_analysis(self,
                            datasets: Dict[str, List[Any]],
                            metric: str = "distribution") -> AnalysisResult:
        """
        Compare multiple datasets.
        """
        findings = []
        
        if metric == "distribution":
            # Compare distributions
            stats = {}
            for name, data in datasets.items():
                numeric = [d for d in data if isinstance(d, (int, float))]
                if numeric:
                    stats[name] = {
                        "count": len(numeric),
                        "mean": mean(numeric),
                        "median": median(numeric),
                        "std": stdev(numeric) if len(numeric) > 1 else 0
                    }
            
            # Find similarities/differences
            if len(stats) >= 2:
                means = [s["mean"] for s in stats.values()]
                max_diff = max(means) - min(means)
                
                findings.append({
                    "type": "distribution_comparison",
                    "datasets": stats,
                    "mean_difference": max_diff,
                    "similarity": "high" if max_diff < stdev(means) else "low"
                })
        
        return AnalysisResult(
            analysis_type=f"comparative_{metric}",
            findings=findings,
            confidence=0.6 if findings else 0.3,
            metadata={"dataset_count": len(datasets)}
        )
    
    def synthesize_findings(self,
                           findings: List[Dict],
                           synthesis_type: str = "summary") -> Dict:
        """
        Synthesize multiple findings into coherent output.
        
        Based on compositional reasoning: build complex conclusions
        from simple components.
        """
        if not findings:
            return {
                "synthesis": "No findings to synthesize",
                "confidence": 0.0,
                "key_insights": []
            }
        
        # Extract key insights
        insights = []
        
        for finding in findings:
            if "type" in finding:
                insights.append(f"{finding['type']}: {json.dumps(finding, default=str)[:100]}...")
        
        # Calculate overall confidence
        confidences = [f.get("confidence", 0.5) for f in findings]
        overall_confidence = mean(confidences) if confidences else 0.5
        
        # Generate synthesis based on type
        if synthesis_type == "summary":
            synthesis = f"Analysis of {len(findings)} findings with {overall_confidence:.0%} confidence."
        elif synthesis_type == "recommendation":
            synthesis = f"Based on analysis, consider reviewing top {min(3, len(findings))} findings."
        elif synthesis_type == "hypothesis":
            synthesis = f"Hypothesis: Patterns suggest systematic relationship (confidence: {overall_confidence:.0%})"
        else:
            synthesis = f"Synthesized {len(findings)} findings."
        
        return {
            "synthesis": synthesis,
            "confidence": overall_confidence,
            "key_insights": insights[:5],  # Top 5 insights
            "finding_count": len(findings)
        }
    
    def generate_hypothesis(self,
                           observations: List[Dict],
                           domain: str = "general") -> Dict:
        """
        Generate hypotheses based on observations.
        
        Inspired by scientific method and ARC-AGI compositional reasoning.
        """
        if not observations:
            return {
                "hypothesis": None,
                "confidence": 0.0,
                "testable": False
            }
        
        # Simple pattern-based hypothesis generation
        patterns = []
        
        # Look for correlations
        for obs in observations:
            if "correlation" in str(obs).lower():
                patterns.append("correlation_detected")
            if "increase" in str(obs).lower():
                patterns.append("increasing_trend")
            if "decrease" in str(obs).lower():
                patterns.append("decreasing_trend")
        
        # Generate hypothesis
        if "correlation_detected" in patterns:
            hypothesis = "Variables show significant correlation suggesting causal relationship"
            confidence = 0.6
        elif "increasing_trend" in patterns and "decreasing_trend" in patterns:
            hypothesis = "System shows conflicting trends requiring further investigation"
            confidence = 0.4
        elif patterns:
            hypothesis = f"Observations suggest: {patterns[0].replace('_', ' ')}"
            confidence = 0.5
        else:
            hypothesis = "Insufficient pattern for strong hypothesis"
            confidence = 0.2
        
        return {
            "hypothesis": hypothesis,
            "confidence": confidence,
            "testable": confidence > 0.5,
            "domain": domain,
            "based_on": len(observations)
        }
    
    def get_analysis_summary(self) -> Dict:
        """Get summary of all analyses performed"""
        return {
            "total_analyses": len(self.analysis_history),
            "types": list(set(a.get("type") for a in self.analysis_history)),
            "recent": self.analysis_history[-5:] if self.analysis_history else []
        }


# Skill function interfaces
def analyze_patterns(data: List[Any], **kwargs) -> Dict:
    """Agent-callable pattern analysis"""
    skill = AnalysisSkill()
    result = skill.analyze_patterns(data, **kwargs)
    return result.to_dict()


def analyze_trends(time_series: List[Tuple[str, float]], **kwargs) -> Dict:
    """Agent-callable trend analysis"""
    skill = AnalysisSkill()
    result = skill.analyze_trends(time_series, **kwargs)
    return result.to_dict()


def synthesize(findings: List[Dict], **kwargs) -> Dict:
    """Agent-callable synthesis"""
    skill = AnalysisSkill()
    return skill.synthesize_findings(findings, **kwargs)


def generate_hypothesis(observations: List[Dict], **kwargs) -> Dict:
    """Agent-callable hypothesis generation"""
    skill = AnalysisSkill()
    return skill.generate_hypothesis(observations, **kwargs)


if __name__ == "__main__":
    # Test the skill
    skill = AnalysisSkill()
    
    # Pattern analysis
    print("=== Pattern Analysis ===")
    data = ["error", "success", "error", "warning", "error", "success", "error"]
    result = skill.analyze_patterns(data, "frequency")
    print(json.dumps(result.to_dict(), indent=2))
    
    # Trend analysis
    print("\n=== Trend Analysis ===")
    time_series = [
        ("2026-01", 100),
        ("2026-02", 120),
        ("2026-03", 115),
        ("2026-04", 140)
    ]
    result = skill.analyze_trends(time_series)
    print(json.dumps(result.to_dict(), indent=2))
    
    # Comparative analysis
    print("\n=== Comparative Analysis ===")
    datasets = {
        "set_a": [1, 2, 3, 4, 5],
        "set_b": [10, 20, 30, 40, 50]
    }
    result = skill.comparative_analysis(datasets, "distribution")
    print(json.dumps(result.to_dict(), indent=2))
    
    # Synthesis
    print("\n=== Synthesis ===")
    synthesis = skill.synthesize_findings([result.to_dict()], "summary")
    print(json.dumps(synthesis, indent=2))
    
    # Hypothesis
    print("\n=== Hypothesis Generation ===")
    observations = [
        {"type": "correlation", "value": 0.8},
        {"type": "increasing", "metric": "performance"}
    ]
    hypothesis = skill.generate_hypothesis(observations)
    print(json.dumps(hypothesis, indent=2))
