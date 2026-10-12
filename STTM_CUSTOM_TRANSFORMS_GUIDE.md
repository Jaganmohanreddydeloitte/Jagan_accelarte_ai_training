# Custom STTM Transformations - Complete Guide

Extend STTM rules with custom Python expressions, regex patterns, and lookup tables.

---

## Overview

The custom transformation system lets users define their own data transformation rules without writing code:

✅ **Python Expressions** — Write formulas using safe Python (e.g., `x * 1.1`)
✅ **Regex Patterns** — Extract or replace using regex (e.g., extract area code from phone)
✅ **Lookup Tables** — Map values using dictionaries (e.g., state codes → names)
✅ **Safe Execution** — Sandboxed evaluation prevents dangerous code
✅ **Visual Editor** — Streamlit UI for creating and testing rules

---

## Quick Start

### 1. Python Expression Rule

```python
from core.sttm_custom_transforms import CustomTransformRuleSet

ruleset = CustomTransformRuleSet("my_sttm", "run-001")

# Add rule: multiply price by 1.1
ruleset.add_python_rule(
    name="scale_price",
    source_column="price",
    target_column="scaled_price",
    expression="x * 1.1",  # x is the input value
    fallback_value=None,   # Value if error
)

# Apply to DataFrame
df = pd.read_csv("data.csv")
result = ruleset.apply_to_dataframe(df)
```

### 2. Regex Rule

```python
# Extract phone area code
ruleset.add_regex_rule(
    name="extract_area_code",
    source_column="phone",
    target_column="area_code",
    pattern=r"(\d{3})-(\d{3})-(\d{4})",  # Regex with groups
    extract_group=1,                      # Extract group 1
    fallback_value="000",
)
```

### 3. Lookup Rule

```python
from core.sttm_custom_transforms import LookupTable

table = LookupTable(
    name="state_codes",
    mapping={"CA": "California", "NY": "New York"},
    default_value="Unknown",
    case_sensitive=False,
)

ruleset.add_lookup_rule(
    name="map_state",
    source_column="state_code",
    target_column="state_name",
    lookup_table=table,
)
```

---

## File Structure

### Core Modules

**core/sttm_custom_transforms.py** (15.6 KB)
- `PythonExpression` — Safe expression evaluation
- `RegexTransform` — Regex pattern matching
- `LookupTable` — Value mapping table
- `CustomTransformRule` — Single rule definition
- `CustomTransformRuleSet` — Collection of rules

**core/sttm_editor.py** (20.5 KB)
- `STTMCustomTransformEditor` — Streamlit UI components
- Python expression editor with validation
- Regex pattern builder
- Lookup table manager
- Rule testing interface

**tests/test_sttm_custom_transforms.py** (23.9 KB)
- 55 comprehensive tests
- Coverage: expressions, regex, lookups, rules, security

---

## Architecture

### Data Flow

```
User Input
    ↓
[Streamlit Editor UI]
    ↓
[Validation]
    ├─ Python: Syntax check + dangerous patterns
    ├─ Regex: Pattern compilation check
    └─ Lookup: Mapping JSON validation
    ↓
[Safe Execution]
    ├─ Python: Sandboxed eval() with whitelisted functions
    ├─ Regex: re.sub/search with error handling
    └─ Lookup: Dictionary lookup with defaults
    ↓
[Result]
    ├─ Success: Transformed value
    └─ Error: Fallback value + audit log
```

### Class Hierarchy

```
CustomTransformRuleSet (collection)
  ├─ rules: Dict[str, CustomTransformRule]
  └─ lookup_tables: Dict[str, LookupTable]

CustomTransformRule (single rule)
  ├─ source_column, target_column
  ├─ transform_type: "python" | "regex" | "lookup"
  └─ transform_config: Dict (type-specific)
      ├─ Python: {name, expression, required_imports}
      ├─ Regex: {name, pattern, replacement, extract_group}
      └─ Lookup: {table_name}

PythonExpression (safe eval)
  ├─ validate() → check for dangerous code
  └─ evaluate(value) → sandboxed execution

RegexTransform (pattern operations)
  ├─ transform(value) → apply transformation
  └─ Can extract groups or replace patterns

LookupTable (value mapping)
  ├─ mapping: Dict[key, value]
  ├─ default_value: fallback
  ├─ case_sensitive: bool
  └─ lookup(value) → mapped value or default
```

---

## Python Expression Rules

### Safe Functions

```python
expr = PythonExpression(name="test", expression="upper(x)")
expr.evaluate("hello")  # → "HELLO"
```

**Built-in functions (whitelisted):**
- `len(x)` — String/list length
- `str(x)` — Convert to string
- `int(x)`, `float(x)` — Numeric conversion
- `abs(x)`, `round(x, decimals)` — Math functions
- `min(x), max(x), sum(x)` — Aggregations
- `upper()`, `lower()`, `strip()` — String ops

**Safe modules:**
- `math` — sqrt, floor, ceil, sin, cos, etc.
- `datetime` — datetime operations
- `json` — JSON operations

### Examples

```python
# Scale values
expr = PythonExpression(
    name="scale",
    expression="x * 1.1",  # Multiply by 1.1
)

# String transformation
expr = PythonExpression(
    name="uppercase",
    expression="x.upper()",  # Uppercase
)

# Conditional logic
expr = PythonExpression(
    name="category",
    expression="'high' if x > 100 else 'low'",  # If/else
)

# Math operations
expr = PythonExpression(
    name="sqrt",
    expression="math.sqrt(x)",  # Square root
    required_imports=["math"],
)

# Complex calculation
expr = PythonExpression(
    name="tax",
    expression="round(x * 1.08, 2)",  # Add tax + round
)
```

### Dangerous Code (BLOCKED)

```python
# These will be REJECTED during validation:
x.__class__          # Private attributes
import os            # Import statements
exec("code")         # Code execution
eval("code")         # Eval
open("file.txt")     # File operations
globals()            # Globals access
locals()             # Locals access
```

### Validation

```python
expr = PythonExpression(name="test", expression="x * 2")
is_valid, msg = expr.validate()

if is_valid:
    result = expr.evaluate(100)  # → 200
else:
    print(f"Invalid: {msg}")
```

---

## Regex Pattern Rules

### Extract Groups

```python
from core.sttm_custom_transforms import RegexTransform

# Extract phone area code from "510-555-1234"
regex = RegexTransform(
    name="area_code",
    pattern=r"(\d{3})-(\d{3})-(\d{4})",
    extract_group=1,  # Extract first group
)
result = regex.transform("510-555-1234")  # → "510"
```

### Replace Pattern

```python
# Replace digits with [NUM]
regex = RegexTransform(
    name="mask_digits",
    pattern=r"\d",
    replacement="[NUM]",
)
result = regex.transform("I have 5 apples")  # → "I have [NUM] apples"
```

### Group Replacement

```python
# Swap parts using group references
regex = RegexTransform(
    name="swap",
    pattern=r"(\w+)-(\w+)",
    replacement=r"\2-\1",  # Swap groups
)
result = regex.transform("hello-world")  # → "world-hello"
```

### Case Insensitive

```python
import re

regex = RegexTransform(
    name="case_insensitive",
    pattern=r"hello",
    replacement="hi",
    flags=re.IGNORECASE,
)
result = regex.transform("HELLO world")  # → "hi world"
```

### Common Patterns

```python
# Email extraction
pattern=r"[\w\.-]+@[\w\.-]+\.\w+"

# Phone number (US)
pattern=r"\(\d{3}\)\s*\d{3}-\d{4}"

# ZIP code
pattern=r"\d{5}(-\d{4})?"

# Date YYYY-MM-DD
pattern=r"\d{4}-\d{2}-\d{2}"

# URL
pattern=r"https?://[^\s]+"
```

---

## Lookup Table Rules

### Basic Mapping

```python
from core.sttm_custom_transforms import LookupTable

table = LookupTable(
    name="status_codes",
    mapping={
        "A": "Active",
        "I": "Inactive",
        "P": "Pending",
    },
    default_value="Unknown",
)

result = table.lookup("A")      # → "Active"
result = table.lookup("X")      # → "Unknown"
```

### Case Insensitive Lookup

```python
table = LookupTable(
    name="states",
    mapping={"CA": "California", "NY": "New York"},
    case_sensitive=False,  # Ignore case
)

result = table.lookup("ca")      # → "California"
result = table.lookup("CA")      # → "California"
result = table.lookup("Ca")      # → "California"
```

### Numeric Keys

```python
table = LookupTable(
    name="grade_codes",
    mapping={
        1: "A",
        2: "B",
        3: "C",
    },
    default_value="F",
)

result = table.lookup(1)         # → "A"
result = table.lookup(99)        # → "F"
```

### In STTM Rule

```python
ruleset.add_lookup_rule(
    name="map_status",
    source_column="status_code",
    target_column="status_desc",
    lookup_table=table,
    fallback_value="Unknown",
)
```

---

## Streamlit UI Editor

### Python Expression Editor

```python
from core.sttm_editor import STTMCustomTransformEditor
import streamlit as st

editor = STTMCustomTransformEditor()
ruleset = editor.render_python_rule_editor()
```

**Features:**
- Expression input with multiline editor
- Module import selector
- Live validation button
- Test interface (enter test value, run expression)
- Syntax highlighting hints

### Regex Pattern Builder

```python
editor.render_regex_rule_editor()
```

**Features:**
- Pattern input with examples
- Group extraction selector
- Replacement string input
- Case sensitivity toggle
- Pattern validation
- Test with sample text

### Lookup Table Manager

```python
editor.render_lookup_rule_editor()
```

**Features:**
- Table name input
- JSON mapping editor
- Case sensitivity toggle
- Mapping validation
- Test with sample key

### Full Editor Interface

```python
# Render complete editor
ruleset = STTMCustomTransformEditor.render_full_editor(
    sttm_name="my_sttm",
    run_id="run-001",
    sample_df=df,  # Optional sample data
)

# Access rules
for rule in ruleset.list_rules():
    print(f"Rule: {rule['name']} ({rule['type']})")
```

### Tabs

1. **Python Rules** — Create/test Python expressions
2. **Regex Rules** — Create/test regex patterns
3. **Lookup Rules** — Create/test lookup tables
4. **Manage & Test** — View all rules, test on DataFrame, export/import

---

## Testing Rules

### Validate All Rules

```python
is_valid, issues = ruleset.validate_all()

if is_valid:
    print("✅ All rules valid")
else:
    for issue in issues:
        print(f"❌ {issue}")
```

### Test Single Value

```python
# Test Python expression
expr = PythonExpression(name="scale", expression="x * 1.1")
result = expr.evaluate(100)
print(f"Result: {result}")  # → 110

# Test regex
regex = RegexTransform(name="area", pattern=r"(\d{3})", extract_group=1)
result = regex.transform("510-555-1234")
print(f"Result: {result}")  # → "510"
```

### Apply to DataFrame

```python
df = pd.DataFrame({
    "price": [100, 200, 300],
    "phone": ["510-555-1234", "415-555-5678", "650-555-9999"],
})

# Apply all rules
result = ruleset.apply_to_dataframe(df)

# Check results
print(result)
```

---

## Export/Import Rules

### Save to JSON

```python
# Export
ruleset.to_json(Path("rules.json"))

# Load
ruleset = CustomTransformRuleSet.from_json(Path("rules.json"))
```

### Serialize/Deserialize

```python
# To dict
data = ruleset.to_dict()

# From dict
ruleset = CustomTransformRuleSet.from_dict(data)
```

### JSON Format

```json
{
  "sttm_name": "my_sttm",
  "run_id": "run-001",
  "rules": {
    "scale_price": {
      "name": "scale_price",
      "source_column": "price",
      "target_column": "scaled_price",
      "transform_type": "python",
      "transform_config": {
        "name": "scale_price",
        "expression": "x * 1.1",
        "required_imports": []
      },
      "fallback_value": null,
      "enabled": true,
      "created_at": "2024-10-07T17:48:06.023Z"
    }
  },
  "lookup_tables": {
    "status_codes": {
      "name": "status_codes",
      "mapping": {"A": "Active", "I": "Inactive"},
      "default_value": "Unknown",
      "case_sensitive": false
    }
  }
}
```

---

## Complete Example

```python
import pandas as pd
from core.sttm_custom_transforms import (
    CustomTransformRuleSet,
    LookupTable,
)

# Create rule set
ruleset = CustomTransformRuleSet("customer_transform", "run-001")

# Add Python rule: calculate discount price
ruleset.add_python_rule(
    name="discount_price",
    source_column="price",
    target_column="price_after_discount",
    expression="round(x * 0.9, 2)",  # 10% discount
)

# Add regex rule: extract area code
ruleset.add_regex_rule(
    name="extract_area_code",
    source_column="phone",
    target_column="area_code",
    pattern=r"(\d{3})-",
    extract_group=1,
    fallback_value="000",
)

# Add lookup rule: map status codes
status_table = LookupTable(
    name="status_map",
    mapping={
        "A": "Active",
        "I": "Inactive",
        "S": "Suspended",
    },
    default_value="Unknown",
    case_sensitive=False,
)
ruleset.add_lookup_rule(
    name="status_lookup",
    source_column="status",
    target_column="status_desc",
    lookup_table=status_table,
)

# Test data
df = pd.DataFrame({
    "price": [100.0, 200.0, 150.0],
    "phone": ["510-555-1234", "415-555-5678", "650-555-9999"],
    "status": ["A", "I", "S"],
})

# Validate
is_valid, issues = ruleset.validate_all()
if is_valid:
    # Apply all rules
    result = ruleset.apply_to_dataframe(df)
    print(result)
    # Output:
    #   price    phone      status area_code price_after_discount status_desc
    # 0 100.0  510-555-1234      A       510                 90.0       Active
    # 1 200.0  415-555-5678      I       415                180.0     Inactive
    # 2 150.0  650-555-9999      S       650                135.0    Suspended
```

---

## Security Features

### Input Validation

✅ **Python Expressions:**
- Syntax validation with `compile()`
- Blacklist dangerous patterns: `__`, `import`, `eval`, `exec`, `open`
- Whitelist only safe built-in functions
- No access to globals/locals

✅ **Regex Patterns:**
- Compile check before use
- Error handling for invalid patterns
- No regex injection possible

✅ **Lookup Tables:**
- JSON validation
- No code execution
- Simple dictionary lookup

### Sandboxing

```python
# Safe execution environment
safe_builtins = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    ...
}

result = eval(
    expression,
    {"__builtins__": {}},  # No builtins
    {"x": value, **safe_builtins},  # Only whitelisted
)
```

---

## Best Practices

### ✅ DO:

1. **Validate before applying:** `ruleset.validate_all()`
2. **Test with sample data:** Use test interface
3. **Use fallback values:** Handle errors gracefully
4. **Name rules clearly:** Use descriptive names
5. **Export rules:** Save to JSON for reuse

### ❌ DON'T:

1. Don't use `__` in expressions (blocked)
2. Don't try to import modules (blocked)
3. Don't access files (blocked)
4. Don't rely on very large expressions (keep simple)
5. Don't skip validation (always validate first)

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid Python syntax" | Bad expression | Check syntax, use `x` for input |
| "Dangerous pattern detected" | Blocked code | Remove `__`, `import`, `eval`, etc. |
| "Invalid regex pattern" | Bad regex | Test regex separately with regex101.com |
| "Lookup table not found" | Missing table | Add table before using in rule |
| "Module not in safe list" | Unsupported import | Use only math, datetime, json |

---

## Summary

✅ **Custom transformations provide:**
- Python expressions with safe evaluation
- Regex patterns for extraction/replacement
- Lookup tables for value mapping
- Streamlit UI for easy rule creation
- Complete validation and testing
- Export/import for reuse
- 55 passing tests

✅ **Users can:**
1. Write custom Python formulas
2. Extract data with regex patterns
3. Map values with lookup tables
4. Test rules before applying
5. Export rules as JSON

✅ **Safe by design:**
- Whitelisted functions only
- Dangerous patterns blocked
- Sandboxed execution
- Error handling built-in

---

See [core/sttm_custom_transforms.py](core/sttm_custom_transforms.py) and [core/sttm_editor.py](core/sttm_editor.py) for implementation.
