"""
Skills module for AGI agents.
Provides tools for web search, file operations, and more.
"""

from .tool_registry import (
    ToolRegistry,
    BaseTool,
    ToolSchema,
    ToolParameter,
    ToolResult,
    ToolCategory,
    ToolRiskLevel,
    get_registry,
    reset_registry,
    WebSearchTool,
    FileReadTool,
    FileWriteTool,
    CalculatorTool
)

from .web_search import (
    WebSearchSkill,
    WebFetchSkill,
    search_web,
    fetch_webpage
)

from .file_operations import (
    FileReadSkill,
    FileWriteSkill,
    FileListSkill,
    FileSearchSkill,
    FileInfoSkill,
    read_file,
    write_file,
    list_files,
    search_files
)

__all__ = [
    # Registry
    "ToolRegistry",
    "BaseTool",
    "ToolSchema",
    "ToolParameter",
    "ToolResult",
    "ToolCategory",
    "ToolRiskLevel",
    "get_registry",
    "reset_registry",
    
    # Built-in tools
    "WebSearchTool",
    "FileReadTool",
    "FileWriteTool",
    "CalculatorTool",
    
    # Web search
    "WebSearchSkill",
    "WebFetchSkill",
    "search_web",
    "fetch_webpage",
    
    # File operations
    "FileReadSkill",
    "FileWriteSkill",
    "FileListSkill",
    "FileSearchSkill",
    "FileInfoSkill",
    "read_file",
    "write_file",
    "list_files",
    "search_files"
]
