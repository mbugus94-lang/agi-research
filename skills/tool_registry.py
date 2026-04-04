"""
Tool Registry and Integration Framework for AGI agents.
Provides unified tool discovery, schema validation, and secure execution.

Based on: Microsoft Agent Governance Toolkit patterns
          OpenAI Function Calling specification
"""

from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import inspect
import time
from datetime import datetime


class ToolCategory(Enum):
    """Categories of tools for organization and permissions."""
    WEB = "web"
    FILE = "file"
    CODE = "code"
    DATA = "data"
    SYSTEM = "system"
    EXTERNAL_API = "external_api"


class ToolRiskLevel(Enum):
    """Risk levels for tool execution (for governance)."""
    SAFE = "safe"           # Read-only, no side effects
    NORMAL = "normal"       # Standard operations with minor side effects
    ELEVATED = "elevated"   # Significant side effects (file writes, API calls)
    CRITICAL = "critical"   # Irreversible or high-impact operations


@dataclass
class ToolParameter:
    """Schema for a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class ToolSchema:
    """Schema definition for a tool (OpenAI function spec compatible)."""
    name: str
    description: str
    parameters: List[ToolParameter]
    category: ToolCategory = ToolCategory.EXTERNAL_API
    risk_level: ToolRiskLevel = ToolRiskLevel.NORMAL
    returns: str = "string"
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic tool use format."""
        input_schema = {"type": "object", "properties": {}, "required": []}
        
        for param in self.parameters:
            input_schema["properties"][param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                input_schema["properties"][param.name]["enum"] = param.enum
            if param.required:
                input_schema["required"].append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": input_schema
        }


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    def __init__(self):
        self._schema = self._define_schema()
        self._execution_count = 0
        self._error_count = 0
    
    @abstractmethod
    def _define_schema(self) -> ToolSchema:
        """Define the tool's schema. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """Execute the tool. Must be implemented by subclasses."""
        pass
    
    @property
    def schema(self) -> ToolSchema:
        return self._schema
    
    @property
    def name(self) -> str:
        return self._schema.name
    
    @property
    def category(self) -> ToolCategory:
        return self._schema.category
    
    @property
    def risk_level(self) -> ToolRiskLevel:
        return self._schema.risk_level
    
    def validate_input(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate input against schema."""
        for param in self._schema.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"
            
            if param.name in kwargs and param.enum is not None:
                if kwargs[param.name] not in param.enum:
                    return False, f"Invalid value for {param.name}: must be one of {param.enum}"
        
        return True, None
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute tool with validation and error handling."""
        start_time = time.time()
        
        # Validate input
        valid, error = self.validate_input(**kwargs)
        if not valid:
            return ToolResult(
                success=False,
                data=None,
                error=error,
                execution_time=time.time() - start_time
            )
        
        try:
            # Execute
            result = self._execute(**kwargs)
            self._execution_count += 1
            
            return ToolResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time,
                metadata={
                    "tool_name": self.name,
                    "execution_number": self._execution_count
                }
            )
        
        except Exception as e:
            self._error_count += 1
            return ToolResult(
                success=False,
                data=None,
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=time.time() - start_time,
                metadata={
                    "tool_name": self.name,
                    "error_type": type(e).__name__
                }
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics."""
        total = self._execution_count + self._error_count
        return {
            "name": self.name,
            "executions": self._execution_count,
            "errors": self._error_count,
            "success_rate": self._execution_count / total if total > 0 else 0
        }


class ToolRegistry:
    """
    Central registry for all available tools.
    Provides discovery, schema management, and governance.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._by_category: Dict[ToolCategory, List[str]] = {
            cat: [] for cat in ToolCategory
        }
        self._execution_history: List[Dict[str, Any]] = []
        self._max_history = 1000
    
    def register(self, tool: BaseTool) -> "ToolRegistry":
        """Register a tool in the registry."""
        self._tools[tool.name] = tool
        self._by_category[tool.category].append(tool.name)
        return self
    
    def register_from_function(
        self,
        func: Callable,
        name: str = None,
        description: str = None,
        category: ToolCategory = ToolCategory.EXTERNAL_API,
        risk_level: ToolRiskLevel = ToolRiskLevel.NORMAL
    ) -> "ToolRegistry":
        """
        Auto-register a function as a tool using introspection.
        
        Args:
            func: The function to register
            name: Tool name (defaults to function name)
            description: Tool description (defaults to docstring)
            category: Tool category
            risk_level: Risk level for governance
        """
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "No description")
        
        # Introspect signature
        sig = inspect.signature(func)
        params = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_type = "array"
                elif param.annotation == dict or param.annotation == Dict:
                    param_type = "object"
            
            required = param.default == inspect.Parameter.empty
            default = param.default if not required else None
            
            params.append(ToolParameter(
                name=param_name,
                type=param_type,
                description=f"Parameter: {param_name}",
                required=required,
                default=default if default != inspect.Parameter.empty else None
            ))
        
        # Create tool schema
        schema = ToolSchema(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            category=category,
            risk_level=risk_level
        )
        
        # Create wrapper class
        class DynamicTool(BaseTool):
            def _define_schema(self) -> ToolSchema:
                return schema
            
            def _execute(self, **kwargs) -> Any:
                return func(**kwargs)
        
        self.register(DynamicTool())
        return self
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(
        self,
        category: ToolCategory = None,
        risk_level: ToolRiskLevel = None
    ) -> List[str]:
        """List available tools with optional filters."""
        tools = list(self._tools.keys())
        
        if category:
            tools = [t for t in tools if self._tools[t].category == category]
        
        if risk_level:
            tools = [t for t in tools if self._tools[t].risk_level == risk_level]
        
        return tools
    
    def get_schemas(self, format: str = "openai") -> List[Dict[str, Any]]:
        """Get all tool schemas in specified format."""
        schemas = []
        for tool in self._tools.values():
            if format == "openai":
                schemas.append(tool.schema.to_openai_schema())
            elif format == "anthropic":
                schemas.append(tool.schema.to_anthropic_schema())
            else:
                schemas.append(tool.schema)
        return schemas
    
    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' not found"
            )
        
        result = tool.execute(**kwargs)
        
        # Record in history
        self._execution_history.append({
            "tool": tool_name,
            "input": kwargs,
            "result": result.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
        
        # Trim history if needed
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]
        
        return result
    
    def get_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent tool execution history."""
        return self._execution_history[-n:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_executions = len(self._execution_history)
        successful = sum(1 for h in self._execution_history if h["result"]["success"])
        
        return {
            "total_tools": len(self._tools),
            "total_executions": total_executions,
            "successful_executions": successful,
            "success_rate": successful / total_executions if total_executions > 0 else 0,
            "by_category": {
                cat.value: len(tools) for cat, tools in self._by_category.items()
            }
        }


# ==================== Built-in Tools ====================

class WebSearchTool(BaseTool):
    """Tool for searching the web."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description="Search the web for information",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="time_range",
                    type="string",
                    description="Time range for results",
                    required=False,
                    enum=["day", "week", "month", "year", "anytime"]
                )
            ],
            category=ToolCategory.WEB,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(self, query: str, time_range: str = "anytime") -> Dict[str, Any]:
        """Execute web search."""
        # Placeholder - actual implementation would call search API
        return {
            "query": query,
            "time_range": time_range,
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "snippet": "..."},
                {"title": "Result 2", "url": "https://example.com/2", "snippet": "..."}
            ]
        }


class FileReadTool(BaseTool):
    """Tool for reading files."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_read",
            description="Read content from a file",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file",
                    required=True
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum lines to read",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(self, path: str, limit: int = None) -> str:
        """Read file contents."""
        with open(path, 'r') as f:
            lines = f.readlines()
            if limit:
                lines = lines[:limit]
            return "".join(lines)


class FileWriteTool(BaseTool):
    """Tool for writing files."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_write",
            description="Write content to a file",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write",
                    required=True
                ),
                ToolParameter(
                    name="append",
                    type="boolean",
                    description="Append to existing file",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.ELEVATED
        )
    
    def _execute(self, path: str, content: str, append: bool = False) -> str:
        """Write to file."""
        mode = 'a' if append else 'w'
        with open(path, mode) as f:
            f.write(content)
        return f"Successfully wrote to {path}"


class CalculatorTool(BaseTool):
    """Tool for mathematical calculations."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="calculator",
            description="Perform mathematical calculations",
            parameters=[
                ToolParameter(
                    name="expression",
                    type="string",
                    description="Mathematical expression to evaluate",
                    required=True
                )
            ],
            category=ToolCategory.DATA,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(self, expression: str) -> Dict[str, Any]:
        """Calculate expression safely."""
        # Safe evaluation using ast
        import ast
        import operator
        
        allowed_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg
        }
        
        def eval_node(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                op = allowed_ops.get(type(node.op))
                if not op:
                    raise ValueError(f"Unsupported operation: {type(node.op)}")
                return op(eval_node(node.left), eval_node(node.right))
            elif isinstance(node, ast.UnaryOp):
                op = allowed_ops.get(type(node.op))
                if not op:
                    raise ValueError(f"Unsupported unary op: {type(node.op)}")
                return op(eval_node(node.operand))
            else:
                raise ValueError(f"Unsupported node type: {type(node)}")
        
        tree = ast.parse(expression, mode='eval')
        result = eval_node(tree.body)
        
        return {
            "expression": expression,
            "result": result
        }


# ==================== Global Registry ====================

_default_registry = None

def get_registry() -> ToolRegistry:
    """Get the default global tool registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        # Register built-in tools
        _default_registry.register(WebSearchTool())
        _default_registry.register(FileReadTool())
        _default_registry.register(FileWriteTool())
        _default_registry.register(CalculatorTool())
    return _default_registry


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _default_registry
    _default_registry = None


if __name__ == "__main__":
    # Demo
    registry = get_registry()
    
    print("=== Available Tools ===")
    for name in registry.list_tools():
        tool = registry.get(name)
        print(f"  • {name} ({tool.category.value}, {tool.risk_level.value})")
    
    print("\n=== OpenAI Schema Format ===")
    print(json.dumps(registry.get_schemas("openai")[0], indent=2))
    
    print("\n=== Tool Execution ===")
    result = registry.execute("calculator", expression="2 + 3 * 4")
    print(f"Calculator result: {result.to_dict()}")
    
    result = registry.execute("web_search", query="AI agents 2026", time_range="week")
    print(f"Search results: {result.data}")
    
    print("\n=== Registry Stats ===")
    print(json.dumps(registry.get_stats(), indent=2))
