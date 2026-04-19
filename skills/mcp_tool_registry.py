"""
MCP (Model Context Protocol) Compliant Tool Registry

Based on 2026 research: MCP standardizes how agents connect to tools and data,
eliminating custom integration work. Projects like OpenAI Agents SDK and
Claude Desktop are explicitly integrating MCP.

Key capabilities:
- Standardized tool definitions with JSON Schema
- Resource management with URI-based addressing
- Prompt templates for consistent tool usage
- Server capabilities negotiation
- Tool discovery and capability advertisement
"""

from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
import hashlib
import inspect
from abc import ABC, abstractmethod


class MCPResourceType(Enum):
    """MCP resource types as per protocol specification."""
    FILE = "file"
    API = "api"
    DATABASE = "database"
    MEMORY = "memory"
    STREAM = "stream"
    TOOL = "tool"


class MCPCapability(Enum):
    """MCP server capabilities."""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    SAMPLING = "sampling"
    ROOTS = "roots"
    COMPLETION = "completion"


@dataclass
class MCPResource:
    """MCP-compliant resource definition."""
    uri: str  # Unique resource identifier
    name: str
    description: str
    mime_type: str
    resource_type: MCPResourceType
    
    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    size_bytes: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
            "type": self.resource_type.value,
            "metadata": self.metadata,
            "size": self.size_bytes,
            "created": self.created_at.isoformat() if self.created_at else None,
            "updated": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class MCPToolParameter:
    """MCP tool parameter definition with JSON Schema support."""
    name: str
    description: str
    param_type: str  # JSON Schema type: string, number, boolean, array, object
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    
    # Extended schema support
    schema_extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_schema(self) -> Dict[str, Any]:
        schema = {
            "type": self.param_type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        schema.update(self.schema_extra)
        return schema


@dataclass
class MCPTool:
    """MCP-compliant tool definition."""
    name: str
    description: str
    parameters: List[MCPToolParameter]
    
    # Handler function
    handler: Optional[Callable] = None
    
    # Metadata
    annotations: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool schema format."""
        required_params = [p.name for p in self.parameters if p.required]
        properties = {p.name: p.to_schema() for p in self.parameters}
        
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required_params
            },
            "annotations": self.annotations,
            "version": self.version,
        }
    
    def get_signature(self) -> str:
        """Generate unique signature for tool."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class MCPPrompt:
    """MCP-compliant prompt template for tool usage."""
    name: str
    description: str
    template: str
    arguments: List[MCPToolParameter] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "arguments": [p.to_schema() for p in self.arguments],
        }
    
    def render(self, **kwargs) -> str:
        """Render prompt with provided arguments."""
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            return f"[Error: Missing argument {e}]"


@dataclass
class MCPServerInfo:
    """MCP server information for capability advertisement."""
    name: str
    version: str
    capabilities: List[MCPCapability]
    instructions: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": [c.value for c in self.capabilities],
            "instructions": self.instructions,
        }


class MCPToolRegistry:
    """
    MCP-compliant tool registry for standardized agent-tool connections.
    
    Implements MCP protocol for:
    - Tool discovery with JSON Schema definitions
    - Resource management with URI addressing
    - Prompt templates for consistent usage
    - Server capability advertisement
    
    Usage:
        registry = MCPToolRegistry("my_agent")
        
        # Register a tool
        registry.register_tool(
            name="search_web",
            description="Search the web for information",
            parameters=[
                MCPToolParameter("query", "Search query", "string"),
                MCPToolParameter("limit", "Max results", "number", required=False, default=10),
            ],
            handler=search_function
        )
        
        # Discover tools
        tools = registry.list_tools()
        
        # Execute tool
        result = registry.execute_tool("search_web", {"query": "AI agents"})
    """
    
    def __init__(self, agent_id: str = "default"):
        self.agent_id = agent_id
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self._handlers: Dict[str, Callable] = {}
        
        # MCP server info
        self.server_info = MCPServerInfo(
            name=f"{agent_id}_mcp_server",
            version="1.0.0",
            capabilities=[MCPCapability.TOOLS, MCPCapability.RESOURCES, MCPCapability.PROMPTS],
            instructions=f"MCP server for {agent_id} agent"
        )
        
        # Execution statistics
        self.execution_stats: Dict[str, Dict[str, Any]] = {}
        
        # Built-in resource: agent memory
        self.register_resource(
            uri="memory://agent/short_term",
            name="Short-term Memory",
            description="Agent's working memory and recent context",
            mime_type="application/json",
            resource_type=MCPResourceType.MEMORY
        )
        
        # Built-in resource: tool registry itself
        self.register_resource(
            uri="resource://registry/tools",
            name="Tool Registry",
            description="List of all available tools",
            mime_type="application/json",
            resource_type=MCPResourceType.TOOL
        )
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: List[MCPToolParameter],
        handler: Optional[Callable] = None,
        annotations: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0"
    ) -> MCPTool:
        """Register a tool with MCP-compliant schema."""
        tool = MCPTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            annotations=annotations or {},
            version=version
        )
        
        self.tools[name] = tool
        if handler:
            self._handlers[name] = handler
        
        # Initialize stats
        self.execution_stats[name] = {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "avg_duration_ms": 0.0,
        }
        
        return tool
    
    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "application/json",
        resource_type: MCPResourceType = MCPResourceType.TOOL,
        metadata: Optional[Dict[str, Any]] = None,
        size_bytes: Optional[int] = None
    ) -> MCPResource:
        """Register a resource with MCP URI scheme."""
        resource = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            resource_type=resource_type,
            metadata=metadata or {},
            size_bytes=size_bytes
        )
        
        self.resources[uri] = resource
        return resource
    
    def register_prompt(
        self,
        name: str,
        description: str,
        template: str,
        arguments: Optional[List[MCPToolParameter]] = None
    ) -> MCPPrompt:
        """Register a prompt template for tool usage."""
        prompt = MCPPrompt(
            name=name,
            description=description,
            template=template,
            arguments=arguments or []
        )
        
        self.prompts[name] = prompt
        return prompt
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools (MCP tools/list equivalent)."""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """List all registered resources."""
        return [resource.to_dict() for resource in self.resources.values()]
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all registered prompts."""
        return [prompt.to_dict() for prompt in self.prompts.values()]
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSON Schema for a tool."""
        tool = self.tools.get(name)
        return tool.to_dict() if tool else None
    
    def get_resource(self, uri: str) -> Optional[MCPResource]:
        """Get a resource by URI."""
        return self.resources.get(uri)
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with provided arguments.
        
        Returns MCP-compliant result format:
        {
            "content": [...],
            "isError": false,
            "duration_ms": ...
        }
        """
        import time
        
        start_time = time.time()
        
        # Validate tool exists
        tool = self.tools.get(tool_name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                "isError": True,
                "duration_ms": 0
            }
        
        # Get handler
        handler = self._handlers.get(tool_name) or tool.handler
        if not handler:
            return {
                "content": [{"type": "text", "text": f"No handler for tool '{tool_name}'"}],
                "isError": True,
                "duration_ms": 0
            }
        
        # Validate required parameters
        missing_params = []
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                missing_params.append(param.name)
        
        if missing_params:
            return {
                "content": [{"type": "text", "text": f"Missing required parameters: {missing_params}"}],
                "isError": True,
                "duration_ms": 0
            }
        
        # Apply defaults
        for param in tool.parameters:
            if param.name not in arguments and param.default is not None:
                arguments[param.name] = param.default
        
        # Execute with timing
        try:
            result = handler(**arguments)
            duration_ms = max(1, int((time.time() - start_time) * 1000))  # Ensure at least 1ms
            
            # Update stats
            self.execution_stats[tool_name]["calls"] += 1
            self.execution_stats[tool_name]["successes"] += 1
            old_avg = self.execution_stats[tool_name]["avg_duration_ms"]
            calls = self.execution_stats[tool_name]["calls"]
            self.execution_stats[tool_name]["avg_duration_ms"] = (old_avg * (calls - 1) + duration_ms) / calls
            
            # Format result as MCP content
            content = self._format_result(result)
            
            return {
                "content": content,
                "isError": False,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = max(1, int((time.time() - start_time) * 1000))  # Ensure at least 1ms
            
            # Update stats
            self.execution_stats[tool_name]["calls"] += 1
            self.execution_stats[tool_name]["failures"] += 1
            
            return {
                "content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}],
                "isError": True,
                "duration_ms": duration_ms
            }
    
    def _format_result(self, result: Any) -> List[Dict[str, Any]]:
        """Format execution result as MCP content items."""
        content = []
        
        if isinstance(result, str):
            content.append({"type": "text", "text": result})
        elif isinstance(result, dict):
            if "text" in result:
                content.append({"type": "text", "text": result["text"]})
            elif "content" in result:
                content.extend(result["content"] if isinstance(result["content"], list) else [{"type": "text", "text": str(result["content"])}])
            else:
                content.append({"type": "text", "text": json.dumps(result, indent=2)})
        elif isinstance(result, list):
            content.append({"type": "text", "text": json.dumps(result, indent=2)})
        else:
            content.append({"type": "text", "text": str(result)})
        
        return content
    
    def get_server_capabilities(self) -> Dict[str, Any]:
        """Get MCP server capabilities."""
        return {
            "server": self.server_info.to_dict(),
            "tools": {
                "count": len(self.tools),
                "list": [t.name for t in self.tools.values()]
            },
            "resources": {
                "count": len(self.resources),
                "list": [r.uri for r in self.resources.values()]
            },
            "prompts": {
                "count": len(self.prompts),
                "list": [p.name for p in self.prompts.values()]
            }
        }
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics for all tools."""
        return {
            "total_calls": sum(s["calls"] for s in self.execution_stats.values()),
            "total_successes": sum(s["successes"] for s in self.execution_stats.values()),
            "total_failures": sum(s["failures"] for s in self.execution_stats.values()),
            "per_tool": self.execution_stats,
            "success_rate": (
                sum(s["successes"] for s in self.execution_stats.values()) /
                max(sum(s["calls"] for s in self.execution_stats.values()), 1)
            )
        }
    
    def create_tool_from_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> MCPTool:
        """Auto-generate MCP tool from Python function signature."""
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "Auto-generated tool")
        
        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default
            required = param.default is inspect.Parameter.empty
            default = param.default if not required else None
            
            # Infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation in (int, float):
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation in (list, List):
                    param_type = "array"
                elif param.annotation in (dict, Dict):
                    param_type = "object"
            
            parameters.append(MCPToolParameter(
                name=param_name,
                description=f"Parameter: {param_name}",
                param_type=param_type,
                required=required,
                default=default
            ))
        
        return self.register_tool(
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            handler=func
        )
    
    def export_mcp_manifest(self) -> str:
        """Export complete MCP manifest as JSON."""
        manifest = {
            "schema_version": "1.0",
            "server": self.server_info.to_dict(),
            "tools": [t.to_dict() for t in self.tools.values()],
            "resources": [r.to_dict() for r in self.resources.values()],
            "prompts": [p.to_dict() for p in self.prompts.values()],
            "stats": self.get_execution_stats()
        }
        return json.dumps(manifest, indent=2)


def create_mcp_registry(agent_id: str = "mcp_agent") -> MCPToolRegistry:
    """Create a new MCP-compliant tool registry."""
    return MCPToolRegistry(agent_id=agent_id)


# Example built-in tool factory
def create_web_search_tool(registry: MCPToolRegistry) -> MCPTool:
    """Create a web search tool following MCP standard."""
    
    def search_handler(query: str, limit: int = 10) -> str:
        # Placeholder - would integrate with actual search
        return f"Search results for '{query}' (limit: {limit})"
    
    return registry.register_tool(
        name="web_search",
        description="Search the web for information using a query",
        parameters=[
            MCPToolParameter("query", "Search query string", "string"),
            MCPToolParameter("limit", "Maximum number of results", "number", required=False, default=10),
        ],
        handler=search_handler,
        annotations={"readOnlyHint": True, "openWorld": True}
    )


def create_code_gen_tool(registry: MCPToolRegistry) -> MCPTool:
    """Create a code generation tool following MCP standard."""
    
    def code_gen_handler(description: str, language: str = "python") -> str:
        # Placeholder - would integrate with actual code generation
        return f"# Generated {language} code for: {description}\n# [Implementation would go here]"
    
    return registry.register_tool(
        name="generate_code",
        description="Generate code based on a description",
        parameters=[
            MCPToolParameter("description", "Description of what the code should do", "string"),
            MCPToolParameter("language", "Programming language", "string", required=False, default="python"),
        ],
        handler=code_gen_handler,
        annotations={"readOnlyHint": False}
    )
