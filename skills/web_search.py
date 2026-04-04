"""
Web search skill for AGI agents.
Integrated with Tool Registry for unified tool management.
"""

import os
import json
from typing import Dict, List, Any, Optional
from .tool_registry import BaseTool, ToolSchema, ToolParameter, ToolCategory, ToolRiskLevel


class WebSearchSkill(BaseTool):
    """
    Web search tool with multiple provider support.
    Supports: Tavily, SerpAPI, or mock mode for testing.
    """
    
    def __init__(self, api_key: str = None, provider: str = "mock"):
        self._api_key = api_key or os.getenv("WEB_SEARCH_API_KEY")
        self._provider = provider
        super().__init__()
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description="Search the web for current information. Returns search results with titles, URLs, and snippets.",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query to execute",
                    required=True
                ),
                ToolParameter(
                    name="time_range",
                    type="string",
                    description="Filter results by time period",
                    required=False,
                    enum=["day", "week", "month", "year", "anytime"]
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results to return (1-10)",
                    required=False
                ),
                ToolParameter(
                    name="include_domains",
                    type="array",
                    description="List of domains to include in search",
                    required=False
                )
            ],
            category=ToolCategory.WEB,
            risk_level=ToolRiskLevel.SAFE,
            examples=[
                {
                    "input": {"query": "latest AI breakthroughs", "time_range": "week"},
                    "output": "Search results for recent AI developments..."
                }
            ]
        )
    
    def _execute(
        self,
        query: str,
        time_range: str = "anytime",
        max_results: int = 5,
        include_domains: List[str] = None
    ) -> Dict[str, Any]:
        """Execute web search using configured provider."""
        
        if self._provider == "tavily" and self._api_key:
            return self._search_tavily(query, time_range, max_results)
        elif self._provider == "serpapi" and self._api_key:
            return self._search_serpapi(query, time_range, max_results)
        else:
            return self._search_mock(query, time_range, max_results)
    
    def _search_tavily(
        self,
        query: str,
        time_range: str,
        max_results: int
    ) -> Dict[str, Any]:
        """Search using Tavily API."""
        import requests
        
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        
        days_map = {
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365,
            "anytime": None
        }
        
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": min(max_results, 10),
            "search_depth": "advanced",
            "include_answer": True
        }
        
        days = days_map.get(time_range)
        if days:
            payload["days"] = days
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        return {
            "query": query,
            "provider": "tavily",
            "answer": data.get("answer"),
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("content"),
                    "score": r.get("score")
                }
                for r in data.get("results", [])
            ]
        }
    
    def _search_serpapi(
        self,
        query: str,
        time_range: str,
        max_results: int
    ) -> Dict[str, Any]:
        """Search using SerpAPI (Google)."""
        import requests
        
        url = "https://serpapi.com/search"
        
        tbs_map = {
            "day": "qdr:d",
            "week": "qdr:w",
            "month": "qdr:m",
            "year": "qdr:y"
        }
        
        params = {
            "q": query,
            "api_key": self._api_key,
            "engine": "google",
            "num": min(max_results, 10)
        }
        
        if time_range in tbs_map:
            params["tbs"] = tbs_map[time_range]
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        organic = data.get("organic_results", [])
        
        return {
            "query": query,
            "provider": "serpapi",
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("link"),
                    "snippet": r.get("snippet"),
                    "position": r.get("position")
                }
                for r in organic[:max_results]
            ]
        }
    
    def _search_mock(
        self,
        query: str,
        time_range: str,
        max_results: int
    ) -> Dict[str, Any]:
        """Mock search for testing without API keys."""
        return {
            "query": query,
            "provider": "mock",
            "note": "Using mock results. Set WEB_SEARCH_API_KEY for real searches.",
            "results": [
                {
                    "title": f"Mock result {i+1} for '{query}'",
                    "url": f"https://example.com/result/{i+1}",
                    "snippet": f"This is a mock search result. In production, this would contain actual content related to: {query}"
                }
                for i in range(min(max_results, 3))
            ]
        }


class WebFetchSkill(BaseTool):
    """Tool for fetching and parsing web pages."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_fetch",
            description="Fetch and extract content from a web page URL",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to fetch",
                    required=True
                ),
                ToolParameter(
                    name="extract_text",
                    type="boolean",
                    description="Extract main text content only",
                    required=False
                ),
                ToolParameter(
                    name="max_length",
                    type="integer",
                    description="Maximum characters to return",
                    required=False
                )
            ],
            category=ToolCategory.WEB,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(
        self,
        url: str,
        extract_text: bool = True,
        max_length: int = 5000
    ) -> Dict[str, Any]:
        """Fetch web page content."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            if extract_text:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator='\n')
                # Clean up whitespace
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                text = '\n'.join(lines)
                if max_length and len(text) > max_length:
                    text = text[:max_length] + "\n... [truncated]"
            else:
                text = response.text[:max_length] if max_length else response.text
            
            return {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string if extract_text and soup.title else None,
                "content": text,
                "content_type": response.headers.get('content-type')
            }
        
        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "content": None
            }


# Convenience function for direct usage
def search_web(query: str, time_range: str = "anytime", max_results: int = 5) -> Dict[str, Any]:
    """Convenience function for web search."""
    skill = WebSearchSkill()
    result = skill.execute(query=query, time_range=time_range, max_results=max_results)
    return result.data if result.success else {"error": result.error}


def fetch_webpage(url: str, max_length: int = 5000) -> str:
    """Convenience function for fetching web pages."""
    skill = WebFetchSkill()
    result = skill.execute(url=url, max_length=max_length)
    if result.success:
        return result.data.get("content", "")
    return f"Error: {result.error}"


if __name__ == "__main__":
    # Demo
    print("=== Web Search Skill Demo ===\n")
    
    # Mock search
    skill = WebSearchSkill()
    result = skill.execute(query="AI agents 2026", time_range="week", max_results=3)
    print(f"Search result: {json.dumps(result.to_dict(), indent=2)}")
    
    print("\n=== Web Fetch Skill Demo ===\n")
    
    fetch_skill = WebFetchSkill()
    schema = fetch_skill.schema.to_openai_schema()
    print(f"Tool schema: {json.dumps(schema, indent=2)}")
