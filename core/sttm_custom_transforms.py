"""
Custom STTM Transformation Rules

Enables users to define custom transformations in the STTM:
- Custom Python expressions (evaluated in a safe sandbox)
- Regex pattern matching and replacement
- Lookup tables for value mapping
- Validation and error handling
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class LookupTable:
    """Mapping table for value transformations"""
    name: str                              # e.g., "state_codes"
    mapping: Dict[str, Any]                # e.g., {"CA": "California"}
    default_value: Optional[Any] = None    # Value if key not found
    case_sensitive: bool = False           # Case-insensitive matching?
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def lookup(self, value: Any) -> Any:
        """Look up value, return mapped value or default"""
        if not self.case_sensitive and isinstance(value, str):
            # Case-insensitive: find matching key
            value_lower = value.lower()
            for key, mapped in self.mapping.items():
                if isinstance(key, str) and key.lower() == value_lower:
                    return mapped
        
        # Case-sensitive or non-string lookup
        if value in self.mapping:
            return self.mapping[value]
        
        return self.default_value

    def to_dict(self) -> Dict:
        """Serialize to dict"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "LookupTable":
        """Deserialize from dict"""
        return cls(**data)


@dataclass
class RegexTransform:
    """Regex pattern matching and replacement"""
    name: str                              # e.g., "extract_phone"
    pattern: str                           # Regex pattern
    replacement: str = ""                  # Replacement string (can use groups: $1, $2, etc.)
    extract_group: Optional[int] = None    # If set, extract this group instead of replacement
    flags: int = 0                         # re.IGNORECASE, re.MULTILINE, etc.
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def transform(self, value: str) -> Optional[str]:
        """Apply regex transformation"""
        try:
            if self.extract_group is not None:
                # Extract specific group
                match = re.search(self.pattern, str(value), self.flags)
                if match:
                    return match.group(self.extract_group)
                return None
            else:
                # Replace pattern with replacement
                return re.sub(self.pattern, self.replacement, str(value), flags=self.flags)
        except Exception as e:
            logger.error(f"Regex transform error: {e}")
            return None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "RegexTransform":
        return cls(**data)


@dataclass
class PythonExpression:
    """Safe Python expression evaluation"""
    name: str                              # e.g., "scale_price"
    expression: str                        # e.g., "x * 1.1" or "len(x)"
    required_imports: List[str] = field(default_factory=list)  # e.g., ["math", "datetime"]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Allowed built-in functions (safe subset)
    SAFE_BUILTINS = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
        "upper": lambda x: str(x).upper(),
        "lower": lambda x: str(x).lower(),
        "strip": lambda x: str(x).strip(),
        "replace": lambda x, old, new: str(x).replace(old, new),
        "split": lambda x, sep: str(x).split(sep),
        "join": lambda sep, lst: sep.join(map(str, lst)),
        "None": None,
        "True": True,
        "False": False,
    }

    # Allowed modules (safe subset)
    SAFE_MODULES = {
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "json": __import__("json"),
    }

    def validate(self) -> tuple[bool, str]:
        """Validate expression for safety"""
        # Check for dangerous patterns
        dangerous_patterns = [
            r"__",           # Private attributes
            r"import ",      # Dynamic imports
            r"exec\(",       # Exec
            r"eval\(",       # Eval
            r"open\(",       # File operations
            r"compile\(",    # Compile
            r"globals\(",    # Globals access
            r"locals\(",     # Locals access
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, self.expression, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"

        # Check for valid Python syntax
        try:
            compile(self.expression, "<string>", "eval")
        except SyntaxError as e:
            return False, f"Invalid Python syntax: {e}"

        return True, "Valid"

    def evaluate(self, value: Any, **kwargs) -> Any:
        """Safely evaluate expression with value as 'x'"""
        is_valid, msg = self.validate()
        if not is_valid:
            raise ValueError(f"Invalid expression: {msg}")

        # Build safe execution environment
        safe_dict = {
            "x": value,
            **self.SAFE_BUILTINS,
            **kwargs,  # Allow passing additional variables
        }

        # Import requested modules
        for module_name in self.required_imports:
            if module_name in self.SAFE_MODULES:
                safe_dict[module_name] = self.SAFE_MODULES[module_name]
            else:
                raise ValueError(f"Module '{module_name}' not in safe list")

        try:
            return eval(self.expression, {"__builtins__": {}}, safe_dict)
        except Exception as e:
            logger.error(f"Expression evaluation error: {e}")
            raise

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "PythonExpression":
        return cls(**data)


@dataclass
class CustomTransformRule:
    """Single custom transformation rule"""
    name: str                              # e.g., "clean_phone_number"
    source_column: str                     # Input column
    target_column: str                     # Output column
    transform_type: str                    # "python", "regex", or "lookup"
    transform_config: Dict[str, Any]       # Type-specific config
    fallback_value: Optional[Any] = None   # Value if transform fails
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def apply_transform(self, value: Any, lookup_tables: Dict[str, LookupTable] = None) -> Any:
        """Apply the transformation"""
        try:
            if self.transform_type == "python":
                expr = PythonExpression(**self.transform_config)
                return expr.evaluate(value)

            elif self.transform_type == "regex":
                regex = RegexTransform(**self.transform_config)
                return regex.transform(value)

            elif self.transform_type == "lookup":
                if lookup_tables is None:
                    return self.fallback_value

                table_name = self.transform_config.get("table_name")
                if table_name not in lookup_tables:
                    return self.fallback_value

                table = lookup_tables[table_name]
                return table.lookup(value)

            else:
                raise ValueError(f"Unknown transform type: {self.transform_type}")

        except Exception as e:
            logger.error(f"Transform error in '{self.name}': {e}")
            return self.fallback_value

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "CustomTransformRule":
        return cls(**data)


class CustomTransformRuleSet:
    """Collection of custom transformation rules for a STTM"""

    def __init__(self, sttm_name: str, run_id: str):
        self.sttm_name = sttm_name
        self.run_id = run_id
        self.rules: Dict[str, CustomTransformRule] = {}
        self.lookup_tables: Dict[str, LookupTable] = {}

    def add_python_rule(
        self,
        name: str,
        source_column: str,
        target_column: str,
        expression: str,
        required_imports: List[str] = None,
        fallback_value: Any = None,
    ) -> None:
        """Add a Python expression transformation rule"""
        py_expr = PythonExpression(
            name=name,
            expression=expression,
            required_imports=required_imports or [],
        )
        is_valid, msg = py_expr.validate()
        if not is_valid:
            raise ValueError(f"Invalid expression: {msg}")

        rule = CustomTransformRule(
            name=name,
            source_column=source_column,
            target_column=target_column,
            transform_type="python",
            transform_config={
                "name": name,
                "expression": expression,
                "required_imports": required_imports or [],
            },
            fallback_value=fallback_value,
        )
        self.rules[name] = rule
        logger.info(f"Added Python rule: {name}")

    def add_regex_rule(
        self,
        name: str,
        source_column: str,
        target_column: str,
        pattern: str,
        replacement: str = "",
        extract_group: Optional[int] = None,
        fallback_value: Any = None,
    ) -> None:
        """Add a regex transformation rule"""
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        rule = CustomTransformRule(
            name=name,
            source_column=source_column,
            target_column=target_column,
            transform_type="regex",
            transform_config={
                "name": name,
                "pattern": pattern,
                "replacement": replacement,
                "extract_group": extract_group,
                "flags": 0,
            },
            fallback_value=fallback_value,
        )
        self.rules[name] = rule
        logger.info(f"Added regex rule: {name}")

    def add_lookup_rule(
        self,
        name: str,
        source_column: str,
        target_column: str,
        lookup_table: LookupTable,
        fallback_value: Any = None,
    ) -> None:
        """Add a lookup table transformation rule"""
        self.lookup_tables[lookup_table.name] = lookup_table

        rule = CustomTransformRule(
            name=name,
            source_column=source_column,
            target_column=target_column,
            transform_type="lookup",
            transform_config={
                "table_name": lookup_table.name,
            },
            fallback_value=fallback_value,
        )
        self.rules[name] = rule
        logger.info(f"Added lookup rule: {name}")

    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all rules to dataframe"""
        result = df.copy()

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            if rule.source_column not in result.columns:
                logger.warning(f"Source column '{rule.source_column}' not found")
                continue

            # Apply transformation to each row
            result[rule.target_column] = result[rule.source_column].apply(
                lambda x: rule.apply_transform(x, self.lookup_tables)
            )

        return result

    def to_dict(self) -> Dict:
        """Serialize to dict"""
        return {
            "sttm_name": self.sttm_name,
            "run_id": self.run_id,
            "rules": {name: rule.to_dict() for name, rule in self.rules.items()},
            "lookup_tables": {name: table.to_dict() for name, table in self.lookup_tables.items()},
        }

    def to_json(self, filepath: Path) -> None:
        """Save to JSON file"""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def from_dict(cls, data: Dict) -> "CustomTransformRuleSet":
        """Deserialize from dict"""
        ruleset = cls(data["sttm_name"], data["run_id"])

        # Load rules
        for rule_data in data.get("rules", {}).values():
            ruleset.rules[rule_data["name"]] = CustomTransformRule.from_dict(rule_data)

        # Load lookup tables
        for table_data in data.get("lookup_tables", {}).values():
            ruleset.lookup_tables[table_data["name"]] = LookupTable.from_dict(table_data)

        return ruleset

    @classmethod
    def from_json(cls, filepath: Path) -> "CustomTransformRuleSet":
        """Load from JSON file"""
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def validate_all(self) -> tuple[bool, List[str]]:
        """Validate all rules"""
        issues = []

        for rule in self.rules.values():
            if rule.transform_type == "python":
                expr = PythonExpression(**rule.transform_config)
                is_valid, msg = expr.validate()
                if not is_valid:
                    issues.append(f"Rule '{rule.name}': {msg}")

            elif rule.transform_type == "regex":
                try:
                    re.compile(rule.transform_config["pattern"])
                except re.error as e:
                    issues.append(f"Rule '{rule.name}': Invalid regex - {e}")

            elif rule.transform_type == "lookup":
                table_name = rule.transform_config.get("table_name")
                if table_name not in self.lookup_tables:
                    issues.append(f"Rule '{rule.name}': Lookup table '{table_name}' not found")

        return len(issues) == 0, issues

    def get_rule(self, name: str) -> Optional[CustomTransformRule]:
        """Get rule by name"""
        return self.rules.get(name)

    def remove_rule(self, name: str) -> None:
        """Remove rule by name"""
        if name in self.rules:
            del self.rules[name]
            logger.info(f"Removed rule: {name}")

    def list_rules(self) -> List[Dict]:
        """List all rules with metadata"""
        return [
            {
                "name": rule.name,
                "source": rule.source_column,
                "target": rule.target_column,
                "type": rule.transform_type,
                "enabled": rule.enabled,
                "created": rule.created_at,
            }
            for rule in self.rules.values()
        ]
