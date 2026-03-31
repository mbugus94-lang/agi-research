"""
Skills package for AGI agents.
Contains capability modules that can be integrated with agents.
"""

from .web_search import WebSearchSkill, WebResearchSkill, create_search_tool, create_research_tool

__all__ = [
    'WebSearchSkill',
    'WebResearchSkill',
    'create_search_tool',
    'create_research_tool'
]
