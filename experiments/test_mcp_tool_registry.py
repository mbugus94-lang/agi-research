"""
Test Suite for MCP (Model Context Protocol) Tool Registry

Validates:
1. Tool registration with JSON Schema
2. Resource management with URI addressing
3. Prompt template handling
4. MCP-compliant execution format
5. Server capability advertisement
6. Tool discovery and introspection
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.mcp_tool_registry import (
    MCPToolRegistry, MCPToolParameter, MCPResource,
    MCPTool, MCPPrompt, MCPServerInfo,
    MCPResourceType, MCPCapability,
    create_mcp_registry, create_web_search_tool, create_code_gen_tool
)


class TestToolRegistration:
    """Test MCP-compliant tool registration."""
    
    def test_basic_tool_registration(self):
        """Test registering a basic tool with parameters."""
        registry = MCPToolRegistry("test_agent")
        
        def dummy_handler(name: str, count: int = 5):
            return f"Hello {name}, count: {count}"
        
        tool = registry.register_tool(
            name="greet",
            description="A greeting tool",
            parameters=[
                MCPToolParameter("name", "Name to greet", "string"),
                MCPToolParameter("count", "Number of greetings", "number", required=False, default=5),
            ],
            handler=dummy_handler
        )
        
        assert tool.name == "greet"
        assert len(tool.parameters) == 2
        assert tool.get_signature() is not None
        assert "greet" in registry.tools
    
    def test_tool_schema_generation(self):
        """Test JSON Schema generation from tool definition."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_tool(
            name="search",
            description="Search tool",
            parameters=[
                MCPToolParameter("query", "Search query", "string"),
                MCPToolParameter("filters", "Optional filters", "array", required=False),
                MCPToolParameter("options", "Search options", "object", required=False, default={}),
            ]
        )
        
        schema = registry.get_tool_schema("search")
        assert schema is not None
        assert schema["name"] == "search"
        assert "inputSchema" in schema
        assert schema["inputSchema"]["type"] == "object"
        assert "query" in schema["inputSchema"]["properties"]
        assert "filters" in schema["inputSchema"]["properties"]
        assert "query" in schema["inputSchema"]["required"]
        assert "filters" not in schema["inputSchema"]["required"]
    
    def test_tool_annotations(self):
        """Test tool metadata annotations."""
        registry = MCPToolRegistry("test_agent")
        
        tool = registry.register_tool(
            name="read_file",
            description="Read a file",
            parameters=[MCPToolParameter("path", "File path", "string")],
            annotations={"readOnlyHint": True, "title": "File Reader"},
            version="2.0.0"
        )
        
        schema = tool.to_dict()
        assert schema["annotations"]["readOnlyHint"] is True
        assert schema["annotations"]["title"] == "File Reader"
        assert schema["version"] == "2.0.0"
    
    def test_enum_parameter(self):
        """Test enum type parameters."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_tool(
            name="configure",
            description="Configure settings",
            parameters=[
                MCPToolParameter(
                    name="mode",
                    description="Configuration mode",
                    param_type="string",
                    enum=["fast", "balanced", "accurate"]
                )
            ]
        )
        
        schema = registry.get_tool_schema("configure")
        assert "enum" in schema["inputSchema"]["properties"]["mode"]
        assert schema["inputSchema"]["properties"]["mode"]["enum"] == ["fast", "balanced", "accurate"]


class TestResourceManagement:
    """Test MCP resource management with URI addressing."""
    
    def test_resource_registration(self):
        """Test registering resources with URI schemes."""
        registry = MCPToolRegistry("test_agent")
        
        resource = registry.register_resource(
            uri="file:///data/documents/report.pdf",
            name="Annual Report",
            description="Company annual report PDF",
            mime_type="application/pdf",
            resource_type=MCPResourceType.FILE,
            size_bytes=2048000
        )
        
        assert resource.uri == "file:///data/documents/report.pdf"
        assert resource.name == "Annual Report"
        assert resource.mime_type == "application/pdf"
        assert resource.size_bytes == 2048000
    
    def test_memory_resource_type(self):
        """Test memory-type resources."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_resource(
            uri="memory://agent/context/short_term",
            name="Short-term Context",
            description="Recent conversation context",
            mime_type="application/json",
            resource_type=MCPResourceType.MEMORY
        )
        
        resource = registry.get_resource("memory://agent/context/short_term")
        assert resource is not None
        assert resource.resource_type == MCPResourceType.MEMORY
    
    def test_resource_listing(self):
        """Test listing all registered resources."""
        registry = MCPToolRegistry("test_agent")
        
        # Built-in resources + custom
        registry.register_resource(
            uri="api://service/data",
            name="Data API",
            description="External data service",
            resource_type=MCPResourceType.API
        )
        
        resources = registry.list_resources()
        # 2 built-in + 1 custom
        assert len(resources) >= 3
        
        uris = [r["uri"] for r in resources]
        assert "api://service/data" in uris
    
    def test_resource_dict_serialization(self):
        """Test resource serialization to dict."""
        resource = MCPResource(
            uri="file:///tmp/test.txt",
            name="Test File",
            description="A test file",
            mime_type="text/plain",
            resource_type=MCPResourceType.FILE,
            size_bytes=1024
        )
        
        d = resource.to_dict()
        assert d["uri"] == "file:///tmp/test.txt"
        assert d["mimeType"] == "text/plain"
        assert d["type"] == "file"
        assert d["size"] == 1024


class TestPromptTemplates:
    """Test MCP prompt templates."""
    
    def test_prompt_registration(self):
        """Test registering prompt templates."""
        registry = MCPToolRegistry("test_agent")
        
        prompt = registry.register_prompt(
            name="summarize",
            description="Summarize text prompt",
            template="Please summarize the following text in {style} style:\n\n{text}",
            arguments=[
                MCPToolParameter("text", "Text to summarize", "string"),
                MCPToolParameter("style", "Summary style", "string", required=False, default="concise")
            ]
        )
        
        assert prompt.name == "summarize"
        assert "{text}" in prompt.template
        assert "{style}" in prompt.template
    
    def test_prompt_rendering(self):
        """Test rendering prompts with arguments."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_prompt(
            name="analyze",
            description="Analyze code",
            template="Analyze this {language} code:\n```{language}\n{code}\n```"
        )
        
        prompt = registry.prompts["analyze"]
        rendered = prompt.render(language="python", code="print('hello')")
        
        assert "python" in rendered
        assert "print('hello')" in rendered
        assert "```python" in rendered
    
    def test_prompt_with_missing_args(self):
        """Test prompt rendering with missing arguments."""
        prompt = MCPPrompt(
            name="test",
            description="Test prompt",
            template="Hello {name}, welcome to {place}"
        )
        
        result = prompt.render(name="Alice")
        assert "Error" in result  # Should report missing 'place'


class TestToolExecution:
    """Test MCP-compliant tool execution."""
    
    def test_successful_execution(self):
        """Test successful tool execution."""
        registry = MCPToolRegistry("test_agent")
        
        def multiply(a: float, b: float) -> float:
            return a * b
        
        registry.register_tool(
            name="multiply",
            description="Multiply two numbers",
            parameters=[
                MCPToolParameter("a", "First number", "number"),
                MCPToolParameter("b", "Second number", "number"),
            ],
            handler=multiply
        )
        
        result = registry.execute_tool("multiply", {"a": 5, "b": 3})
        
        assert result["isError"] is False
        assert result["duration_ms"] > 0
        assert len(result["content"]) > 0
    
    def test_execution_with_default_params(self):
        """Test execution with default parameter values."""
        registry = MCPToolRegistry("test_agent")
        
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"
        
        registry.register_tool(
            name="greet",
            description="Greet someone",
            parameters=[
                MCPToolParameter("name", "Name", "string"),
                MCPToolParameter("greeting", "Greeting text", "string", required=False, default="Hello"),
            ],
            handler=greet
        )
        
        # Without default param
        result1 = registry.execute_tool("greet", {"name": "Alice"})
        assert "Hello" in result1["content"][0]["text"]
        
        # With custom greeting
        result2 = registry.execute_tool("greet", {"name": "Bob", "greeting": "Hi"})
        assert "Hi" in result2["content"][0]["text"]
    
    def test_missing_required_parameter(self):
        """Test execution with missing required parameter."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_tool(
            name="require_input",
            description="Requires input",
            parameters=[MCPToolParameter("input", "Required input", "string")],
            handler=lambda input: input
        )
        
        result = registry.execute_tool("require_input", {})
        
        assert result["isError"] is True
        assert "Missing required parameters" in result["content"][0]["text"]
    
    def test_nonexistent_tool(self):
        """Test execution of non-existent tool."""
        registry = MCPToolRegistry("test_agent")
        
        result = registry.execute_tool("nonexistent", {})
        
        assert result["isError"] is True
        assert "not found" in result["content"][0]["text"]
    
    def test_execution_error_handling(self):
        """Test handling of execution errors."""
        registry = MCPToolRegistry("test_agent")
        
        def failing_tool(x: int) -> str:
            raise ValueError("Intentional error")
        
        registry.register_tool(
            name="failing_tool",
            description="This tool always fails",
            parameters=[MCPToolParameter("x", "Input", "number")],
            handler=failing_tool
        )
        
        result = registry.execute_tool("failing_tool", {"x": 1})
        
        assert result["isError"] is True
        assert "Error executing" in result["content"][0]["text"]
        assert "Intentional error" in result["content"][0]["text"]
    
    def test_execution_stats_tracking(self):
        """Test that execution statistics are tracked."""
        registry = MCPToolRegistry("test_agent")
        
        def simple_tool():
            return "ok"
        
        registry.register_tool(
            name="simple",
            description="Simple tool",
            parameters=[],
            handler=simple_tool
        )
        
        # Execute multiple times
        registry.execute_tool("simple", {})
        registry.execute_tool("simple", {})
        registry.execute_tool("simple", {})
        
        stats = registry.execution_stats["simple"]
        assert stats["calls"] == 3
        assert stats["successes"] == 3
        assert stats["avg_duration_ms"] > 0


class TestServerCapabilities:
    """Test MCP server capability advertisement."""
    
    def test_server_info(self):
        """Test server information structure."""
        registry = MCPToolRegistry("my_agent")
        
        assert registry.server_info.name == "my_agent_mcp_server"
        assert MCPCapability.TOOLS in registry.server_info.capabilities
    
    def test_capabilities_report(self):
        """Test full capabilities report."""
        registry = MCPToolRegistry("test_agent")
        
        # Register some tools
        registry.register_tool(
            name="tool1",
            description="Tool 1",
            parameters=[],
            handler=lambda: "result1"
        )
        registry.register_tool(
            name="tool2",
            description="Tool 2",
            parameters=[],
            handler=lambda: "result2"
        )
        
        registry.register_resource(
            uri="data://resource1",
            name="Resource 1",
            description="A resource",
            resource_type=MCPResourceType.TOOL
        )
        
        registry.register_prompt(
            name="prompt1",
            description="Prompt 1",
            template="Hello {name}"
        )
        
        caps = registry.get_server_capabilities()
        
        assert caps["server"]["name"] == "test_agent_mcp_server"
        assert caps["tools"]["count"] == 2
        assert "tool1" in caps["tools"]["list"]
        assert "tool2" in caps["tools"]["list"]
        assert caps["resources"]["count"] >= 3  # 2 built-in + 1 custom
        assert caps["prompts"]["count"] == 1
    
    def test_builtin_resources(self):
        """Test that built-in resources are automatically registered."""
        registry = MCPToolRegistry("test_agent")
        
        resources = registry.list_resources()
        
        # Should have built-in memory and registry resources
        uris = [r["uri"] for r in resources]
        assert "memory://agent/short_term" in uris
        assert "resource://registry/tools" in uris


class TestAutoToolGeneration:
    """Test auto-generating tools from functions."""
    
    def test_from_function_basic(self):
        """Test auto-generation from simple function."""
        registry = MCPToolRegistry("test_agent")
        
        def calculate_area(length: float, width: float) -> float:
            """Calculate the area of a rectangle."""
            return length * width
        
        tool = registry.create_tool_from_function(calculate_area)
        
        assert tool.name == "calculate_area"
        assert tool.description == "Calculate the area of a rectangle."
        assert len(tool.parameters) == 2
        
        # Check parameter types inferred
        schema = tool.to_dict()
        assert schema["inputSchema"]["properties"]["length"]["type"] == "number"
        assert "length" in schema["inputSchema"]["required"]
        assert "width" in schema["inputSchema"]["required"]
    
    def test_from_function_defaults(self):
        """Test auto-generation with default values."""
        registry = MCPToolRegistry("test_agent")
        
        def greet(name: str, greeting: str = "Hello", count: int = 1) -> str:
            """Greet a person."""
            return f"{greeting}, {name}! " * count
        
        tool = registry.create_tool_from_function(greet)
        
        schema = tool.to_dict()
        props = schema["inputSchema"]["properties"]
        
        assert "name" in schema["inputSchema"]["required"]
        assert "greeting" not in schema["inputSchema"]["required"]
        assert "count" not in schema["inputSchema"]["required"]
        
        assert props["greeting"]["default"] == "Hello"
        assert props["count"]["default"] == 1


class TestBuiltInTools:
    """Test built-in tool factories."""
    
    def test_web_search_tool(self):
        """Test web search tool factory."""
        registry = MCPToolRegistry("test_agent")
        
        tool = create_web_search_tool(registry)
        
        assert tool.name == "web_search"
        assert tool.annotations.get("readOnlyHint") is True
        
        # Test execution
        result = registry.execute_tool("web_search", {"query": "AI agents"})
        assert result["isError"] is False
        assert "AI agents" in result["content"][0]["text"]
    
    def test_code_gen_tool(self):
        """Test code generation tool factory."""
        registry = MCPToolRegistry("test_agent")
        
        tool = create_code_gen_tool(registry)
        
        assert tool.name == "generate_code"
        
        # Test execution
        result = registry.execute_tool("generate_code", {
            "description": "Print hello world",
            "language": "python"
        })
        assert result["isError"] is False
        assert "python" in result["content"][0]["text"]


class TestManifestExport:
    """Test MCP manifest export."""
    
    def test_manifest_structure(self):
        """Test manifest JSON structure."""
        registry = MCPToolRegistry("test_agent")
        
        registry.register_tool(
            name="manifest_test",
            description="Test tool",
            parameters=[MCPToolParameter("x", "Input", "string")],
            handler=lambda x: x
        )
        
        manifest_json = registry.export_mcp_manifest()
        import json
        manifest = json.loads(manifest_json)
        
        assert manifest["schema_version"] == "1.0"
        assert "server" in manifest
        assert "tools" in manifest
        assert "resources" in manifest
        assert "prompts" in manifest
        assert "stats" in manifest
        
        # Check tool in manifest
        tool_names = [t["name"] for t in manifest["tools"]]
        assert "manifest_test" in tool_names


class TestMCPIntegration:
    """Test end-to-end MCP integration scenarios."""
    
    def test_full_workflow(self):
        """Test complete MCP workflow: register, discover, execute."""
        registry = MCPToolRegistry("integration_agent")
        
        # 1. Register tools
        registry.register_tool(
            name="analyze_data",
            description="Analyze data set",
            parameters=[
                MCPToolParameter("data", "Data to analyze", "array"),
                MCPToolParameter("method", "Analysis method", "string", 
                              required=False, default="average"),
            ],
            handler=lambda data, method: {"result": f"Analyzed {len(data)} items using {method}"}
        )
        
        # 2. Discover tools
        tools = registry.list_tools()
        assert len(tools) > 0
        
        # 3. Get schema
        schema = registry.get_tool_schema("analyze_data")
        assert schema["inputSchema"]["properties"]["method"]["default"] == "average"
        
        # 4. Execute
        result = registry.execute_tool("analyze_data", {
            "data": [1, 2, 3, 4, 5],
            "method": "sum"
        })
        
        assert result["isError"] is False
        assert "5 items" in result["content"][0]["text"]
        
        # 5. Check stats
        stats = registry.get_execution_stats()
        assert stats["total_calls"] >= 1
        assert stats["total_successes"] >= 1
    
    def test_multiple_tool_types(self):
        """Test registry with multiple tool types."""
        registry = MCPToolRegistry("multi_agent")
        
        # Read-only tool
        registry.register_tool(
            name="read",
            description="Read data",
            parameters=[MCPToolParameter("path", "Path", "string")],
            handler=lambda path: f"Data from {path}",
            annotations={"readOnlyHint": True}
        )
        
        # Write tool
        registry.register_tool(
            name="write",
            description="Write data",
            parameters=[
                MCPToolParameter("path", "Path", "string"),
                MCPToolParameter("content", "Content", "string")
            ],
            handler=lambda path, content: f"Wrote to {path}",
            annotations={"readOnlyHint": False}
        )
        
        # List and verify
        tools = registry.list_tools()
        schemas = {t["name"]: t for t in tools}
        
        assert schemas["read"]["annotations"]["readOnlyHint"] is True
        assert schemas["write"]["annotations"]["readOnlyHint"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
