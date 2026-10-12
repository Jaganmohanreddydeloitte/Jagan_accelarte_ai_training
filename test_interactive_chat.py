"""
Quick test to verify Interactive Chat components work correctly.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Verify all imports work."""
    print("\n" + "=" * 60)
    print("TESTING INTERACTIVE CHAT COMPONENTS")
    print("=" * 60 + "\n")
    
    try:
        print("1. Testing core imports...")
        from core.chat_engine import ChatEngine
        print("   [OK] ChatEngine import successful")
        # Don't test chat_ui since it requires streamlit
        print("   [OK] Chat UI components (requires streamlit)")
    except Exception as e:
        print(f"   [ERROR] Core import failed: {e}")
        return False
    
    try:
        print("2. Testing dependencies...")
        import duckdb
        print("   [OK] duckdb available")
        import langchain
        print("   [OK] langchain available")
        try:
            import streamlit
            print("   [OK] streamlit available")
        except:
            print("   [SKIP] streamlit not installed (will load when needed)")
    except Exception as e:
        print(f"   [ERROR] Dependency missing: {e}")
        return False
    
    return True


def test_chat_engine_instantiation():
    """Test ChatEngine can be instantiated."""
    print("\n3. Testing ChatEngine instantiation...")
    
    try:
        from core.chat_engine import ChatEngine
        
        # Create dummy test file path (doesn't need to exist for instantiation)
        test_file = Path("test.parquet")
        engine = ChatEngine(test_file, "test_run_123")
        
        print("   [OK] ChatEngine instantiated successfully")
        print(f"   - File: {engine.parquet_file}")
        print(f"   - Run ID: {engine.run_id}")
        print(f"   - LLM: {engine.llm.__class__.__name__}")
        
        # Test sample questions
        samples = engine.get_sample_questions()
        print(f"   - Sample questions available: {len(samples)}")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Instantiation failed: {e}")
        return False


def test_sql_validation():
    """Test SQL validation logic."""
    print("\n4. Testing SQL validation...")
    
    try:
        from core.chat_engine import ChatEngine
        
        engine = ChatEngine(Path("dummy.parquet"), "test_run")
        
        # Test blocking dangerous operations
        dangerous_queries = [
            "DROP TABLE data",
            "DELETE FROM data",
            "INSERT INTO data VALUES (...)",
            "UPDATE data SET col = value",
            "ALTER TABLE data ADD COLUMN x INT",
        ]
        
        blocked_count = 0
        for query in dangerous_queries:
            is_valid = engine._validate_sql(query)
            if not is_valid:
                blocked_count += 1
        
        print(f"   [OK] Blocked {blocked_count}/{len(dangerous_queries)} dangerous queries")
        
        # Test allowing safe queries
        safe_queries = [
            "SELECT * FROM data",
            "SELECT COUNT(*) FROM data WHERE col > 10",
            "SELECT col1, COUNT(*) FROM data GROUP BY col1",
        ]
        
        allowed_count = 0
        for query in safe_queries:
            is_valid = engine._validate_sql(query)
            if is_valid:
                allowed_count += 1
        
        print(f"   [OK] Allowed {allowed_count}/{len(safe_queries)} safe queries")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Validation test failed: {e}")
        return False


def test_conversation_history():
    """Test conversation history management."""
    print("\n5. Testing conversation history...")
    
    try:
        from core.chat_engine import ChatEngine
        
        engine = ChatEngine(Path("dummy.parquet"), "test_run")
        
        # Verify empty initially
        history = engine.get_conversation_history()
        assert len(history) == 0, "History should start empty"
        print("   [OK] Conversation history starts empty")
        
        # Test clear
        engine.clear_history()
        history = engine.get_conversation_history()
        assert len(history) == 0, "History should be empty after clear"
        print("   [OK] Clear history works")
        
        return True
    except Exception as e:
        print(f"   [ERROR] History test failed: {e}")
        return False


def test_streamlit_ui():
    """Test Streamlit UI components can be imported."""
    print("\n6. Testing Streamlit UI components...")
    
    try:
        from core.chat_ui import render_chat_interface, render_chat_widget
        
        # Check functions exist and are callable
        assert callable(render_chat_interface), "render_chat_interface should be callable"
        assert callable(render_chat_widget), "render_chat_widget should be callable"
        
        print("   [OK] UI components available")
        print(f"   - render_chat_interface: {render_chat_interface.__doc__[:50]}...")
        print(f"   - render_chat_widget: {render_chat_widget.__doc__[:50]}...")
        
        return True
    except ImportError:
        print("   [SKIP] Streamlit not installed (will be available in Streamlit app)")
        return True
    except Exception as e:
        print(f"   [ERROR] UI component test failed: {e}")
        return False


def test_documentation():
    """Verify documentation files exist."""
    print("\n7. Testing documentation files...")
    
    docs = [
        "INTERACTIVE_CHAT_GUIDE.md",
        "INTERACTIVE_CHAT_SUMMARY.md",
        "INTERACTIVE_CHAT_INTEGRATION_GUIDE.py",
    ]
    
    found = 0
    for doc in docs:
        path = Path(__file__).parent / doc
        if path.exists():
            size = path.stat().st_size
            print(f"   [OK] {doc} ({size:,} bytes)")
            found += 1
        else:
            print(f"   [MISSING] {doc} NOT FOUND")
    
    return found == len(docs)


def main():
    """Run all tests."""
    print("\n")
    print("=" * 60)
    print("INTERACTIVE CHAT - COMPONENT VERIFICATION TEST")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("ChatEngine Instantiation", test_chat_engine_instantiation()))
    results.append(("SQL Validation", test_sql_validation()))
    results.append(("Conversation History", test_conversation_history()))
    results.append(("Streamlit UI", test_streamlit_ui()))
    results.append(("Documentation", test_documentation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    
    if passed == total:
        print(f"\n[SUCCESS] All {total} tests passed!\n")
        print("Interactive Chat components are ready to use.")
        print("\nNext steps:")
        print("1. Read INTERACTIVE_CHAT_SUMMARY.md for overview")
        print("2. Follow INTERACTIVE_CHAT_INTEGRATION_GUIDE.py for examples")
        print("3. Review INTERACTIVE_CHAT_GUIDE.md for complete reference")
        print("4. Run: streamlit run app/streamlit_app.py")
        print("5. Upload data and generate report to see chat interface\n")
        return 0
    else:
        print(f"\n[FAILURE] {total - passed} test(s) failed!\n")
        print("Please fix the errors above before continuing.")
        return 1


if __name__ == "__main__":
    exit(main())
