"""
Web Search Skill

Capability for information retrieval via web search.
Implements the skill interface for the agent framework.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Single search result"""
    title: str
    url: str
    snippet: str
    source: str


class WebSearchSkill:
    """
    Skill for searching the web.
    
    Integrates with Zo's web search capability.
    """
    
    def __init__(self):
        self.name = "web_search"
        self.description = "Search the web for information"
        self.capabilities = ["search", "research", "find information"]
    
    def can_handle(self, action: str, context: Dict[str, Any]) -> bool:
        """
        Check if this skill can handle the action.
        
        Matches:
        - Actions starting with "search"
        - Actions containing "find", "lookup", "research"
        - Goal-related context keywords
        """
        action_lower = action.lower()
        
        # Direct matches
        if any(action_lower.startswith(prefix) for prefix in ["search", "lookup", "find"]):
            return True
        
        if "research" in action_lower or "information" in action_lower:
            return True
        
        # Check context
        goal = context.get("goal", "").lower()
        if any(term in goal for term in ["research", "find", "search", "lookup"]):
            return True
        
        return False
    
    def execute(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute web search.
        
        Note: In actual execution, this would integrate with Zo's web_search tool.
        For the skill framework, we define the interface.
        """
        # Extract search query from action
        query = self._extract_query(action, context)
        
        if not query:
            return {
                "success": False,
                "error": "Could not extract search query",
                "action": action
            }
        
        # This would call the actual web search
        # For now, return the query that would be searched
        return {
            "success": True,
            "query": query,
            "note": "Search query ready for execution",
            "results": [],  # Would be populated by actual search
            "result_count": 0,
            "metadata": {
                "time_range": context.get("time_range", "anytime"),
                "search_type": "general"
            }
        }
    
    def _extract_query(self, action: str, context: Dict[str, Any]) -> Optional[str]:
        """Extract search query from action string."""
        # Try to extract query after common prefixes
        prefixes = ["search:", "search ", "lookup:", "lookup ", "find:", "find "]
        
        action_lower = action.lower()
        for prefix in prefixes:
            if prefix in action_lower:
                parts = action.split(":", 1) if ":" in action else action.split(" ", 1)
                if len(parts) > 1:
                    return parts[1].strip()
        
        # Fall back to using the goal
        goal = context.get("goal", "")
        if goal:
            return goal
        
        return None
    
    def learn_from(self, experience: Dict[str, Any]) -> None:
        """
        Learn from search experience.
        
        Could improve:
        - Query extraction patterns
        - Search parameter selection
        - Result filtering
        """
        # Record for future improvement
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities
        }
