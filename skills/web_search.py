"""
Web Search Skill

Provides AGI agent with web search capabilities.
Based on 2026 research: tool use and MCP integration are critical for agent capabilities.
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "web"
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "timestamp": self.timestamp
        }


class WebSearchSkill:
    """
    Web search capability for the AGI agent.
    
    In production, this would integrate with search APIs.
    For testing/development, provides mock/search interface.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.search_history: List[Dict] = []
        self.max_results = 10
    
    def search(self, query: str, 
               num_results: int = 5,
               time_range: str = "anytime") -> Dict:
        """
        Execute web search.
        
        Returns structured results for agent consumption.
        
        Note: In production, integrates with:
        - SerpAPI
        - Tavily
        - Perplexity
        - Bing/Google APIs
        """
        if not query.strip():
            return {
                "success": False,
                "error": "Empty query",
                "results": []
            }
        
        # Record search
        search_record = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "time_range": time_range
        }
        self.search_history.append(search_record)
        
        # Placeholder for actual search implementation
        # In production, this calls external search APIs
        results = self._mock_search(query, num_results)
        
        return {
            "success": True,
            "query": query,
            "time_range": time_range,
            "results_count": len(results),
            "results": [r.to_dict() for r in results]
        }
    
    def _mock_search(self, query: str, num_results: int) -> List[SearchResult]:
        """Mock search for testing - returns dummy results"""
        # In production, this would call actual search API
        return [
            SearchResult(
                title=f"Mock Result {i+1} for: {query[:30]}...",
                url=f"https://example.com/result/{i}",
                snippet=f"This is a mock search result snippet for query: {query[:50]}..."
            )
            for i in range(min(num_results, 3))  # Return max 3 mock results
        ]
    
    def deep_research(self, query: str, 
                      follow_up_questions: int = 3) -> Dict:
        """
        Deep research mode: multiple searches with follow-ups.
        
        Inspired by OpenAI's deep research agent patterns.
        """
        # Initial search
        initial = self.search(query)
        
        if not initial["success"]:
            return initial
        
        # Generate follow-up questions based on results
        follow_ups = self._generate_follow_ups(query, initial["results"])
        
        # Search follow-ups
        follow_up_results = []
        for fq in follow_ups[:follow_up_questions]:
            result = self.search(fq)
            if result["success"]:
                follow_up_results.append({
                    "query": fq,
                    "results": result["results"]
                })
        
        return {
            "success": True,
            "original_query": query,
            "initial_results": initial["results"],
            "follow_up_questions": follow_ups,
            "follow_up_results": follow_up_results,
            "total_searches": 1 + len(follow_up_results)
        }
    
    def _generate_follow_ups(self, original: str, 
                            results: List[Dict]) -> List[str]:
        """Generate follow-up questions based on search results"""
        # In production, uses LLM to generate relevant follow-ups
        return [
            f"What are the latest developments in {original}?",
            f"How does {original} compare to alternatives?",
            f"What are the challenges with {original}?"
        ]
    
    def summarize_results(self, results: List[Dict], 
                         max_length: int = 500) -> str:
        """
        Summarize search results into coherent text.
        
        Returns condensed information for agent consumption.
        """
        if not results:
            return "No results to summarize."
        
        summaries = []
        for r in results[:5]:  # Top 5 results
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            summaries.append(f"- {title}: {snippet}")
        
        full_summary = "\n".join(summaries)
        
        if len(full_summary) > max_length:
            full_summary = full_summary[:max_length-3] + "..."
        
        return full_summary
    
    def get_search_history(self) -> List[Dict]:
        """Return search history"""
        return self.search_history
    
    def clear_history(self) -> None:
        """Clear search history"""
        self.search_history = []


# Skill function interface for agent integration
def web_search(query: str, **kwargs) -> Dict:
    """Agent-callable web search skill"""
    skill = WebSearchSkill()
    return skill.search(query, **kwargs)


def deep_research(query: str, **kwargs) -> Dict:
    """Agent-callable deep research skill"""
    skill = WebSearchSkill()
    return skill.deep_research(query, **kwargs)


def summarize_search(results: List[Dict], **kwargs) -> str:
    """Agent-callable summarize skill"""
    skill = WebSearchSkill()
    return skill.summarize_results(results, **kwargs)


if __name__ == "__main__":
    # Test the skill
    skill = WebSearchSkill()
    
    # Basic search
    print("=== Basic Search ===")
    result = skill.search("AGI latest research", num_results=3)
    print(json.dumps(result, indent=2))
    
    # Deep research
    print("\n=== Deep Research ===")
    deep = skill.deep_research("AI agent architecture 2026", follow_up_questions=2)
    print(f"Total searches: {deep['total_searches']}")
    print(f"Follow-up questions: {deep['follow_up_questions']}")
    
    # Summarize
    print("\n=== Summarize ===")
    summary = skill.summarize_results(result["results"])
    print(summary)
