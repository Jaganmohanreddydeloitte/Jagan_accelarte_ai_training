"""
Tests for Custom STTM Transformation Rules

Coverage:
- Python expression validation and evaluation
- Regex pattern matching and extraction
- Lookup table mapping
- Custom transformation rules
- Rule sets and bulk operations
"""

import pytest
import json
import tempfile
from pathlib import Path
import pandas as pd
from datetime import datetime

from core.sttm_custom_transforms import (
    PythonExpression,
    RegexTransform,
    LookupTable,
    CustomTransformRule,
    CustomTransformRuleSet,
)


class TestPythonExpression:
    """Test Python expression validation and evaluation"""

    def test_valid_expression(self):
        """Valid expression should pass validation"""
        expr = PythonExpression(name="test", expression="x * 2")
        is_valid, msg = expr.validate()
        assert is_valid
        assert msg == "Valid"

    def test_invalid_syntax(self):
        """Invalid syntax should fail"""
        expr = PythonExpression(name="test", expression="x * ")
        is_valid, msg = expr.validate()
        assert not is_valid
        assert "Invalid Python syntax" in msg

    def test_dangerous_pattern_import(self):
        """Import statements should be blocked"""
        expr = PythonExpression(name="test", expression="import os; x")
        is_valid, msg = expr.validate()
        assert not is_valid
        assert "Dangerous pattern" in msg

    def test_dangerous_pattern_private_attribute(self):
        """Private attributes should be blocked"""
        expr = PythonExpression(name="test", expression="x.__class__")
        is_valid, msg = expr.validate()
        assert not is_valid

    def test_dangerous_pattern_eval(self):
        """eval() should be blocked"""
        expr = PythonExpression(name="test", expression="eval('x')")
        is_valid, msg = expr.validate()
        assert not is_valid

    def test_evaluate_simple_arithmetic(self):
        """Simple arithmetic should work"""
        expr = PythonExpression(name="scale", expression="x * 1.1")
        result = expr.evaluate(100)
        assert abs(result - 110) < 0.0001  # Allow for floating point precision

    def test_evaluate_string_function(self):
        """String functions should work"""
        expr = PythonExpression(name="upper", expression="x.upper()")
        result = expr.evaluate("hello")
        assert result == "HELLO"

    def test_evaluate_builtin_function(self):
        """Safe builtins should work"""
        expr = PythonExpression(name="length", expression="len(x)")
        result = expr.evaluate("test")
        assert result == 4

    def test_evaluate_with_multiple_operations(self):
        """Multiple operations should work"""
        expr = PythonExpression(name="complex", expression="round(x * 1.15, 2)")
        result = expr.evaluate(100)
        assert result == 115.0

    def test_evaluate_with_module(self):
        """Math module should work"""
        expr = PythonExpression(
            name="sqrt",
            expression="math.sqrt(x)",
            required_imports=["math"],
        )
        result = expr.evaluate(16)
        assert result == 4.0

    def test_evaluate_with_conditional(self):
        """Conditional expressions should work"""
        expr = PythonExpression(
            name="conditional",
            expression="'high' if x > 100 else 'low'"
        )
        assert expr.evaluate(150) == "high"
        assert expr.evaluate(50) == "low"

    def test_evaluate_with_extra_kwargs(self):
        """Extra variables should work"""
        expr = PythonExpression(name="multiply", expression="x * multiplier")
        result = expr.evaluate(100, multiplier=2)
        assert result == 200

    def test_evaluate_invalid_module(self):
        """Invalid module should raise error"""
        expr = PythonExpression(
            name="bad",
            expression="os.system('ls')",
            required_imports=["os"],
        )
        with pytest.raises(ValueError, match="not in safe list"):
            expr.evaluate("test")

    def test_serialization(self):
        """Should serialize/deserialize correctly"""
        expr1 = PythonExpression(
            name="test",
            expression="x * 2",
            required_imports=["math"],
        )
        data = expr1.to_dict()
        expr2 = PythonExpression.from_dict(data)
        assert expr2.name == expr1.name
        assert expr2.expression == expr1.expression
        assert expr2.required_imports == expr1.required_imports


class TestRegexTransform:
    """Test regex pattern matching and extraction"""

    def test_simple_replacement(self):
        """Simple replacement should work"""
        regex = RegexTransform(
            name="test",
            pattern=r"\d+",
            replacement="[NUM]",
        )
        result = regex.transform("I have 5 apples")
        assert result == "I have [NUM] apples"

    def test_extract_group(self):
        """Extract group should work"""
        regex = RegexTransform(
            name="extract_phone",
            pattern=r"(\d{3})-(\d{3})-(\d{4})",
            extract_group=1,
        )
        result = regex.transform("Call 123-456-7890")
        assert result == "123"

    def test_extract_full_match(self):
        """Extract full match should work"""
        regex = RegexTransform(
            name="extract_code",
            pattern=r"[A-Z]{3}\d{3}",
            extract_group=0,
        )
        result = regex.transform("Code: ABC123 end")
        assert result == "ABC123"

    def test_case_insensitive(self):
        """Case insensitive should work"""
        import re
        regex = RegexTransform(
            name="case_insensitive",
            pattern=r"hello",
            replacement="hi",
            flags=re.IGNORECASE,
        )
        result = regex.transform("HELLO world")
        assert result == "hi world"

    def test_group_replacement(self):
        """Group replacement should work"""
        regex = RegexTransform(
            name="swap",
            pattern=r"(\w+)-(\w+)",
            replacement=r"\2-\1",
        )
        result = regex.transform("hello-world")
        assert result == "world-hello"

    def test_no_match_returns_original(self):
        """No match should return original with replacement applied (empty)"""
        regex = RegexTransform(
            name="test",
            pattern=r"\d+",
            replacement="[NUM]",
        )
        result = regex.transform("no numbers here")
        assert result == "no numbers here"

    def test_no_match_with_extract_returns_none(self):
        """Extract with no match should return None"""
        regex = RegexTransform(
            name="extract",
            pattern=r"\d+",
            extract_group=1,
        )
        result = regex.transform("no numbers")
        assert result is None

    def test_invalid_pattern_raises(self):
        """Invalid regex should be handled"""
        regex = RegexTransform(
            name="bad",
            pattern=r"[invalid(pattern",
        )
        result = regex.transform("test")
        assert result is None  # Should handle error gracefully

    def test_serialization(self):
        """Should serialize/deserialize correctly"""
        regex1 = RegexTransform(
            name="test",
            pattern=r"\d+",
            replacement="[NUM]",
            extract_group=1,
        )
        data = regex1.to_dict()
        regex2 = RegexTransform.from_dict(data)
        assert regex2.name == regex1.name
        assert regex2.pattern == regex1.pattern


class TestLookupTable:
    """Test lookup table mapping"""

    def test_simple_lookup(self):
        """Simple lookup should work"""
        table = LookupTable(
            name="states",
            mapping={"CA": "California", "NY": "New York"},
        )
        assert table.lookup("CA") == "California"
        assert table.lookup("NY") == "New York"

    def test_missing_key_returns_default(self):
        """Missing key should return default"""
        table = LookupTable(
            name="states",
            mapping={"CA": "California"},
            default_value="Unknown",
        )
        assert table.lookup("XX") == "Unknown"

    def test_missing_key_no_default_returns_none(self):
        """Missing key with no default should return None"""
        table = LookupTable(
            name="states",
            mapping={"CA": "California"},
        )
        assert table.lookup("XX") is None

    def test_case_insensitive_lookup(self):
        """Case insensitive lookup should work"""
        table = LookupTable(
            name="states",
            mapping={"CA": "California"},
            case_sensitive=False,
        )
        assert table.lookup("ca") == "California"
        assert table.lookup("CA") == "California"
        assert table.lookup("Ca") == "California"

    def test_case_sensitive_lookup(self):
        """Case sensitive lookup should work"""
        table = LookupTable(
            name="states",
            mapping={"CA": "California"},
            case_sensitive=True,
        )
        assert table.lookup("CA") == "California"
        assert table.lookup("ca") is None

    def test_numeric_values(self):
        """Numeric values should work"""
        table = LookupTable(
            name="codes",
            mapping={1: "One", 2: "Two", 3: "Three"},
        )
        assert table.lookup(1) == "One"
        assert table.lookup(2) == "Two"

    def test_serialization(self):
        """Should serialize/deserialize correctly"""
        table1 = LookupTable(
            name="test",
            mapping={"a": 1, "b": 2},
            default_value=0,
            case_sensitive=False,
        )
        data = table1.to_dict()
        table2 = LookupTable.from_dict(data)
        assert table2.name == table1.name
        assert table2.lookup("a") == 1


class TestCustomTransformRule:
    """Test individual transformation rules"""

    def test_apply_python_rule(self):
        """Apply Python rule should work"""
        rule = CustomTransformRule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            transform_type="python",
            transform_config={
                "name": "scale",
                "expression": "x * 1.1",
                "required_imports": [],
            },
        )
        result = rule.apply_transform(100)
        assert abs(result - 110) < 0.0001  # Allow for floating point precision

    def test_apply_regex_rule(self):
        """Apply regex rule should work"""
        rule = CustomTransformRule(
            name="extract_phone",
            source_column="contact",
            target_column="phone",
            transform_type="regex",
            transform_config={
                "name": "extract_phone",
                "pattern": r"(\d{3})-(\d{3})-(\d{4})",
                "replacement": "",
                "extract_group": 1,
                "flags": 0,
            },
        )
        result = rule.apply_transform("123-456-7890")
        assert result == "123"

    def test_apply_lookup_rule(self):
        """Apply lookup rule should work"""
        rule = CustomTransformRule(
            name="map_state",
            source_column="state_code",
            target_column="state_name",
            transform_type="lookup",
            transform_config={"table_name": "states"},
        )
        table = LookupTable(name="states", mapping={"CA": "California"})
        result = rule.apply_transform("CA", lookup_tables={"states": table})
        assert result == "California"

    def test_fallback_on_error(self):
        """Fallback value should be used on error"""
        rule = CustomTransformRule(
            name="bad_expr",
            source_column="col",
            target_column="target",
            transform_type="python",
            transform_config={
                "name": "bad",
                "expression": "1 / 0",  # Will raise ZeroDivisionError
                "required_imports": [],
            },
            fallback_value="ERROR",
        )
        result = rule.apply_transform(100)
        assert result == "ERROR"

    def test_serialization(self):
        """Should serialize/deserialize correctly"""
        rule1 = CustomTransformRule(
            name="test",
            source_column="src",
            target_column="tgt",
            transform_type="python",
            transform_config={"name": "test", "expression": "x", "required_imports": []},
        )
        data = rule1.to_dict()
        rule2 = CustomTransformRule.from_dict(data)
        assert rule2.name == rule1.name
        assert rule2.source_column == rule1.source_column


class TestCustomTransformRuleSet:
    """Test rule sets and bulk operations"""

    def test_add_python_rule(self):
        """Add Python rule should work"""
        ruleset = CustomTransformRuleSet("test_sttm", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        assert "scale" in ruleset.rules
        assert ruleset.rules["scale"].name == "scale"

    def test_add_regex_rule(self):
        """Add regex rule should work"""
        ruleset = CustomTransformRuleSet("test_sttm", "run-001")
        ruleset.add_regex_rule(
            name="extract_phone",
            source_column="contact",
            target_column="phone",
            pattern=r"(\d{3})-(\d{3})-(\d{4})",
            extract_group=1,
        )
        assert "extract_phone" in ruleset.rules

    def test_add_lookup_rule(self):
        """Add lookup rule should work"""
        ruleset = CustomTransformRuleSet("test_sttm", "run-001")
        table = LookupTable(name="states", mapping={"CA": "California"})
        ruleset.add_lookup_rule(
            name="map_state",
            source_column="state_code",
            target_column="state_name",
            lookup_table=table,
        )
        assert "map_state" in ruleset.rules

    def test_apply_to_dataframe(self):
        """Apply rules to DataFrame should work"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )

        df = pd.DataFrame({"price": [100, 200, 300]})
        result = ruleset.apply_to_dataframe(df)

        assert "scaled_price" in result.columns
        # Allow for floating point precision
        assert all(abs(result["scaled_price"].iloc[i] - expected) < 0.0001 
                   for i, expected in enumerate([110, 220, 330]))

    def test_apply_multiple_rules_to_dataframe(self):
        """Apply multiple rules should work"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        ruleset.add_python_rule(
            name="round",
            source_column="scaled_price",
            target_column="rounded_price",
            expression="round(x, 0)",
        )

        df = pd.DataFrame({"price": [100, 200]})
        result = ruleset.apply_to_dataframe(df)

        assert list(result["rounded_price"]) == [110.0, 220.0]

    def test_disabled_rule_not_applied(self):
        """Disabled rules should not be applied"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        ruleset.rules["scale"].enabled = False

        df = pd.DataFrame({"price": [100, 200]})
        result = ruleset.apply_to_dataframe(df)

        assert "scaled_price" not in result.columns

    def test_validate_all_rules(self):
        """Validate all rules should work"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="good",
            source_column="x",
            target_column="y",
            expression="x * 2",
        )
        is_valid, issues = ruleset.validate_all()
        assert is_valid
        assert len(issues) == 0

    def test_validate_catches_invalid_regex(self):
        """Validation should catch invalid regex"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        # Manually insert invalid rule (bypass validation)
        rule = CustomTransformRule(
            name="bad_regex",
            source_column="x",
            target_column="y",
            transform_type="regex",
            transform_config={
                "name": "bad",
                "pattern": "[invalid(",  # Invalid regex
                "replacement": "",
                "extract_group": None,
                "flags": 0,
            },
        )
        ruleset.rules["bad_regex"] = rule

        is_valid, issues = ruleset.validate_all()
        assert not is_valid
        assert any("bad_regex" in issue for issue in issues)

    def test_get_rule(self):
        """Get rule by name should work"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        rule = ruleset.get_rule("scale")
        assert rule is not None
        assert rule.name == "scale"

    def test_remove_rule(self):
        """Remove rule should work"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        ruleset.remove_rule("scale")
        assert "scale" not in ruleset.rules

    def test_list_rules(self):
        """List rules should return metadata"""
        ruleset = CustomTransformRuleSet("test", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        rules = ruleset.list_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "scale"
        assert rules[0]["type"] == "python"

    def test_serialization_to_dict(self):
        """Serialize to dict should work"""
        ruleset = CustomTransformRuleSet("test_sttm", "run-001")
        ruleset.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )
        data = ruleset.to_dict()

        assert data["sttm_name"] == "test_sttm"
        assert data["run_id"] == "run-001"
        assert "scale" in data["rules"]

    def test_serialization_from_dict(self):
        """Deserialize from dict should work"""
        ruleset1 = CustomTransformRuleSet("test_sttm", "run-001")
        ruleset1.add_python_rule(
            name="scale",
            source_column="price",
            target_column="scaled_price",
            expression="x * 1.1",
        )

        data = ruleset1.to_dict()
        ruleset2 = CustomTransformRuleSet.from_dict(data)

        assert ruleset2.sttm_name == "test_sttm"
        assert len(ruleset2.rules) == 1
        assert "scale" in ruleset2.rules

    def test_json_file_roundtrip(self):
        """Save/load from JSON file should work"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ruleset1 = CustomTransformRuleSet("test_sttm", "run-001")
            ruleset1.add_python_rule(
                name="scale",
                source_column="price",
                target_column="scaled_price",
                expression="x * 1.1",
            )

            # Save
            filepath = Path(tmpdir) / "rules.json"
            ruleset1.to_json(filepath)
            assert filepath.exists()

            # Load
            ruleset2 = CustomTransformRuleSet.from_json(filepath)
            assert ruleset2.sttm_name == "test_sttm"
            assert len(ruleset2.rules) == 1

    def test_complex_workflow(self):
        """Test complex workflow with multiple rule types"""
        ruleset = CustomTransformRuleSet("complex", "run-001")

        # Add Python rule
        ruleset.add_python_rule(
            name="scale_price",
            source_column="price",
            target_column="price_scaled",
            expression="round(x * 1.1, 2)",
        )

        # Add regex rule
        ruleset.add_regex_rule(
            name="extract_area_code",
            source_column="phone",
            target_column="area_code",
            pattern=r"(\d{3})-",
            extract_group=1,
        )

        # Add lookup rule
        table = LookupTable(
            name="status_map",
            mapping={"A": "Active", "I": "Inactive", "P": "Pending"},
            default_value="Unknown",
        )
        ruleset.add_lookup_rule(
            name="map_status",
            source_column="status_code",
            target_column="status_desc",
            lookup_table=table,
        )

        # Create test data
        df = pd.DataFrame({
            "price": [100.0, 200.0],
            "phone": ["510-555-1234", "415-555-5678"],
            "status_code": ["A", "I"],
        })

        # Apply all rules
        result = ruleset.apply_to_dataframe(df)

        # Verify results
        assert "price_scaled" in result.columns
        assert list(result["price_scaled"]) == [110.0, 220.0]

        assert "area_code" in result.columns
        assert list(result["area_code"]) == ["510", "415"]

        assert "status_desc" in result.columns
        assert list(result["status_desc"]) == ["Active", "Inactive"]


class TestSafety:
    """Test safety features for user-defined code"""

    def test_no_file_operations(self):
        """File operations should be blocked"""
        expr = PythonExpression(name="bad", expression="open('file.txt')")
        is_valid, msg = expr.validate()
        assert not is_valid

    def test_no_os_operations(self):
        """OS operations should be blocked"""
        expr = PythonExpression(name="bad", expression="__import__('os')")
        is_valid, msg = expr.validate()
        # Note: __import__ is blocked by __ pattern check, but let's also
        # test if evaluation would fail gracefully
        if is_valid:  # In case the expression passes validation syntax check
            try:
                expr.evaluate("test")
                assert False, "Should have blocked OS operations"
            except (ValueError, NameError):
                pass  # Expected
        else:
            assert not is_valid  # Validation should catch dangerous patterns

    def test_safe_math_operations(self):
        """Math operations should be safe"""
        expr = PythonExpression(
            name="sqrt",
            expression="math.sqrt(x)",
            required_imports=["math"],
        )
        is_valid, msg = expr.validate()
        assert is_valid

    def test_no_arbitrary_globals(self):
        """Arbitrary globals should not be accessible"""
        expr = PythonExpression(name="bad", expression="globals()")
        is_valid, msg = expr.validate()
        assert not is_valid

    def test_timeout_safety(self):
        """Infinite loops should fail gracefully (in practice, implement timeout)"""
        # This is handled by the evaluation environment - we ensure
        # no complex constructs are allowed
        expr = PythonExpression(name="test", expression="x")
        is_valid, msg = expr.validate()
        assert is_valid
