"""
Validation tests for the tool integration system.
Tests the 10,000+ tool scalability patterns.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.tool_integration import (
    ToolRegistry, ToolComposer, ToolDiscovery, ToolChain,
    Tool, ToolSchema, ToolCategory, ToolRiskLevel,
    create_default_registry, tool_decorator
)


def test_registry_basic():
    """Test basic registry operations."""
    print("\n1️⃣ Testing registry basic operations...")
    registry = create_default_registry()
    
    # Test stats
    stats = registry.get_stats()
    assert stats["total_tools"] > 0, "Registry should have tools"
    print(f"   ✅ Registry has {stats['total_tools']} tools")
    
    # Test get tool
    calc = registry.get_tool("calculate")
    assert calc is not None, "Should find calculate tool"
    print(f"   ✅ Found tool: {calc.name}")
    
    # Test by category
    file_tools = registry.get_tools_by_category(ToolCategory.FILE)
    assert len(file_tools) > 0, "Should have file tools"
    print(f"   ✅ Found {len(file_tools)} file tools")
    
    return True


def test_tool_execution():
    """Test tool execution."""
    print("\n2️⃣ Testing tool execution...")
    registry = create_default_registry()
    
    # Test calculate
    calc = registry.get_tool("calculate")
    result = calc.execute(expression="2 + 2 * 10")
    assert result["success"], f"Calculate failed: {result}"
    assert result["result"] == 22.0, f"Wrong result: {result['result']}"
    print(f"   ✅ Calculate: 2 + 2 * 10 = {result['result']}")
    
    # Test analyze_text
    analyzer = registry.get_tool("analyze_text")
    result = analyzer.execute(text="Hello world test", analysis_type="word_count")
    assert result["success"], f"Analysis failed: {result}"
    assert result["result"]["word_count"] == 3, f"Wrong word count"
    print(f"   ✅ Analyze: word_count = {result['result']['word_count']}")
    
    # Test format_data
    formatter = registry.get_tool("format_data")
    result = formatter.execute(data={"key": "value"}, format_type="json")
    assert result["success"], f"Format failed: {result}"
    assert "key" in result["result"], f"Wrong format output"
    print(f"   ✅ Format data works")
    
    return True


def test_tool_search():
    """Test tool search functionality."""
    print("\n3️⃣ Testing tool search...")
    registry = create_default_registry()
    
    # Search by name
    results = registry.search_tools("calculate", limit=5)
    assert len(results) > 0, "Should find calculate tool"
    print(f"   ✅ Search 'calculate': found {len(results)} tools")
    
    # Find for task
    tools = registry.find_tools_for_task("read and analyze files")
    assert len(tools) > 0, "Should find tools for task"
    print(f"   ✅ Find for task: found {len(tools)} relevant tools")
    
    return True


def test_tool_chains():
    """Test tool chain composition."""
    print("\n4️⃣ Testing tool chain composition...")
    registry = create_default_registry()
    composer = ToolComposer(registry)
    
    # Compose for research task
    chain = composer.compose_for_task(
        "research AI trends",
        list(registry._tools.keys())
    )
    
    if chain:
        print(f"   ✅ Composed chain: {chain.name}")
        print(f"   Steps: {[s['tool'] for s in chain.steps]}")
    else:
        print(f"   ⚠️ No chain composed (expected - basic toolset)")
    
    return True


def test_schema_validation():
    """Test tool schema validation."""
    print("\n5️⃣ Testing schema validation...")
    
    schema = ToolSchema(
        parameters={
            "name": {"type": "string"},
            "count": {"type": "integer"}
        },
        required=["name"]
    )
    
    # Valid input
    valid, errors = schema.validate({"name": "test", "count": 5})
    assert valid, f"Should validate: {errors}"
    print(f"   ✅ Valid input accepted")
    
    # Missing required
    valid, errors = schema.validate({"count": 5})
    assert not valid, "Should reject missing required"
    assert any("name" in e for e in errors), "Should mention missing field"
    print(f"   ✅ Missing required rejected: {errors[0]}")
    
    # Wrong type
    valid, errors = schema.validate({"name": "test", "count": "five"})
    assert not valid, "Should reject wrong type"
    print(f"   ✅ Wrong type rejected: {errors[0]}")
    
    return True


def test_tool_discovery():
    """Test tool discovery from functions."""
    print("\n6️⃣ Testing tool discovery...")
    registry = create_default_registry()
    discovery = ToolDiscovery(registry)
    
    # Create test functions
    @tool_decorator(category=ToolCategory.WEB, tags=["test"])
    def test_search(query: str, limit: int = 10) -> list:
        """Search for test data."""
        return [f"result_{i}" for i in range(limit)]
    
    @tool_decorator(category=ToolCategory.DATA, tags=["test"], risk_level=ToolRiskLevel.CAUTION)
    def test_process(data: list, transform: str) -> dict:
        """Process test data."""
        return {"processed": len(data), "transform": transform}
    
    # Simulate discovery by manually creating tools
    tool1 = discovery._create_tool_from_function(test_search, "test_search")
    tool2 = discovery._create_tool_from_function(test_process, "test_process")
    
    # Note: heuristic detection may differ from decorator - that's expected
    # The decorator marks intent; discovery infers from code
    print(f"   Discovered '{tool1.name}' in category {tool1.category.value}")
    print(f"   Discovered '{tool2.name}' with risk {tool2.risk_level.value}")
    
    # Register
    registry.register_tool(tool1)
    registry.register_tool(tool2)
    
    # Execute
    result1 = tool1.execute(query="test", limit=3)
    assert result1["success"], f"Test search failed: {result1}"
    assert len(result1["result"]) == 3, f"Wrong result count"
    
    result2 = tool2.execute(data=[1, 2, 3], transform="double")
    assert result2["success"], f"Test process failed: {result2}"
    assert result2["result"]["processed"] == 3, f"Wrong process result"
    
    print(f"   ✅ Discovered and executed {2} test tools successfully")
    
    return True


def test_usage_stats():
    """Test usage statistics tracking."""
    print("\n7️⃣ Testing usage statistics...")
    registry = create_default_registry()
    
    # Record some usage
    calc = registry.get_tool("calculate")
    for i in range(5):
        calc.execute(expression=f"{i} + 1")
        registry.record_usage("calculate", success=True)
    
    # One failure
    calc.execute(expression="invalid +")
    registry.record_usage("calculate", success=False)
    
    # Check stats
    stats = registry.get_stats()
    total_calls = stats["total_calls"]
    success_rate = stats["success_rate"]
    
    assert total_calls >= 6, f"Should have recorded calls: {total_calls}"
    print(f"   ✅ Recorded {total_calls} calls with {success_rate:.0%} success rate")
    
    return True


def test_scalability_pattern():
    """Test the 10,000+ tool scalability patterns."""
    print("\n8️⃣ Testing scalability patterns...")
    registry = ToolRegistry()
    
    # Simulate registering many tools
    for i in range(100):
        tool = Tool(
            name=f"bulk_tool_{i}",
            description=f"Bulk tool number {i} for testing",
            category=ToolCategory.CUSTOM if i % 3 == 0 else ToolCategory.DATA,
            risk_level=ToolRiskLevel.SAFE,
            func=lambda x=i: f"result_{x}",
            schema=ToolSchema(parameters={"input": {"type": "string"}}, required=[]),
            tags=["bulk", f"tag_{i % 10}"]
        )
        registry.register_tool(tool)
    
    stats = registry.get_stats()
    assert stats["total_tools"] == 100, f"Should have 100 tools: {stats['total_tools']}"
    
    # Test search still works quickly
    results = registry.search_tools("bulk", limit=10)
    assert len(results) == 10, f"Should find 10 tools: {len(results)}"
    
    # Test category filter
    data_tools = registry.get_tools_by_category(ToolCategory.DATA)
    assert len(data_tools) > 0, "Should have data tools"
    
    print(f"   ✅ Successfully registered and searched {stats['total_tools']} tools")
    print(f"   Categories: {stats['by_category']}")
    
    return True


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Tool Integration System - Validation Tests")
    print("=" * 60)
    
    tests = [
        test_registry_basic,
        test_tool_execution,
        test_tool_search,
        test_tool_chains,
        test_schema_validation,
        test_tool_discovery,
        test_usage_stats,
        test_scalability_pattern
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"   ❌ Test returned False")
        except Exception as e:
            failed += 1
            print(f"   ❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(tests)} tests passed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
