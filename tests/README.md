# IDAMP Pipeline Testing Guide

This directory contains comprehensive unit and integration tests for the Intent-Driven Agentic Medallion Pipeline (IDAMP).

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── test_pipeline.py     # All unit and integration tests
└── README.md           # This file
```

## Test Categories

### 1. Core Configuration Tests (`TestCoreConfig`)
- Validates that all required directories are created
- Verifies path resolution
- Tests environment setup

### 2. Audit Logger Tests (`TestAuditLogger`)
- Tests JSONL logging functionality
- Validates log file creation
- Tests arbitrary keyword argument storage
- Verifies timestamp inclusion

### 3. Observability Tests (`TestAgentTrace`)
- Tests agent trace initialization
- Validates chainable setters
- Tests duration calculation
- Tests failure handling

### 4. Pipeline State Tests (`TestPipelineState`)
- Validates state schema
- Tests state persistence

### 5. Memory Tests (`TestMemory`)
- Tests document storage
- Tests memory querying
- Tests error handling

### 6. Integration Tests (`TestIntegration`)
- Tests interaction between AuditLogger and AgentTrace
- Tests state persistence with file operations

### 7. Streamlit Helper Tests (`TestStreamlitHelpers`)
- Tests DataFrame manipulation for STTM editing
- Tests audit entry formatting
- Tests CSS class generation for UI

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Class
```bash
pytest tests/test_pipeline.py::TestAuditLogger
```

### Run Specific Test
```bash
pytest tests/test_pipeline.py::TestAuditLogger::test_audit_logger_writes_jsonl
```

### Run Tests with Verbose Output
```bash
pytest -v
```

### Run Tests with Coverage Report
```bash
pytest --cov=. --cov-report=html
```

### Run Only Integration Tests
```bash
pytest -m integration
```

### Run Tests and Stop on First Failure
```bash
pytest -x
```

## Dependencies

To run tests, install the test dependencies:

```bash
pip install pytest pytest-cov pandas pydantic
```

## Test Fixtures

Common fixtures available in all tests:

- `temp_run_id`: Generates a unique run ID for testing
- `sample_audit_entry`: Sample audit log entry
- `sample_pipeline_state`: Sample pipeline state dictionary
- `test_project_root`: Project root directory
- `test_data_dir`: Test data directory

## Writing New Tests

### Test Template
```python
class TestNewFeature:
    """Test description."""
    
    def test_specific_behavior(self, temp_run_id):
        """Test that describes what should happen."""
        # Arrange
        obj = MyClass(temp_run_id)
        
        # Act
        result = obj.do_something()
        
        # Assert
        assert result == expected_value
```

### Best Practices

1. **Naming**: Use `test_` prefix for test functions and `Test` for test classes
2. **Documentation**: Always include docstrings explaining what's being tested
3. **Isolation**: Each test should be independent and not rely on other tests
4. **Fixtures**: Use pytest fixtures for shared setup/teardown
5. **Mocking**: Mock external dependencies (LLMs, databases, APIs)
6. **Assertions**: Use clear, specific assertions

## Test Coverage

Current coverage includes:

| Component | Coverage |
|-----------|----------|
| core/config.py | ✓ Paths and directory creation |
| core/audit.py | ✓ JSONL logging, retrieval |
| core/observability.py | ✓ Trace initialization, duration |
| core/state.py | ✓ State schema validation |
| core/memory.py | ✓ Document storage, querying |
| app/streamlit_app.py | ✓ Helper functions, UI logic |

## Known Limitations

1. **ChromaDB Tests**: Tests are skipped if ChromaDB is not installed
2. **LLM Tests**: LLM calls are not tested directly; use mocks in integration tests
3. **UI Tests**: Streamlit UI tests are limited to helper function testing

## Continuous Integration

Tests are designed to run in CI/CD pipelines. To set up:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    pip install -r requirements-test.txt
    pytest --cov=. --cov-report=xml
    
- name: Upload Coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### ImportError: No module named 'core'
**Solution**: Run tests from the project root directory
```bash
cd /path/to/Accelerate_with_ai_lab
pytest
```

### Tests Hang on LLM Calls
**Solution**: Use mocks or skip LLM tests in CI
```bash
pytest -m "not slow"
```

### ChromaDB Not Found
**Solution**: Install ChromaDB or skip memory tests
```bash
pip install chromadb
# OR
pytest -k "not memory"
```

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass: `pytest`
3. Achieve ≥80% coverage on new code
4. Document test assumptions

## Support

For issues or questions about testing:
1. Check this README
2. Review existing test examples
3. Check pytest documentation: https://docs.pytest.org
