"""
STTM Custom Transformation Editor UI

Streamlit components for editing custom transformation rules:
- Python expression editor with validation
- Regex pattern builder
- Lookup table manager
- Rule testing interface
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List, Any
import json
from datetime import datetime

from core.sttm_custom_transforms import (
    CustomTransformRuleSet,
    CustomTransformRule,
    PythonExpression,
    RegexTransform,
    LookupTable,
)


class STTMCustomTransformEditor:
    """Streamlit UI for STTM custom transformations"""

    # Sidebar session state keys
    KEY_CURRENT_RULE = "sttm_current_rule"
    KEY_RULESET = "sttm_ruleset"
    KEY_TEST_DATA = "sttm_test_data"

    @staticmethod
    def initialize_session(sttm_name: str, run_id: str) -> None:
        """Initialize session state for STTM editor"""
        if KEY_RULESET := STTMCustomTransformEditor.KEY_RULESET not in st.session_state:
            st.session_state[STTMCustomTransformEditor.KEY_RULESET] = CustomTransformRuleSet(
                sttm_name, run_id
            )

    @staticmethod
    def render_python_rule_editor() -> Optional[Dict[str, Any]]:
        """UI for creating/editing Python expression rules"""
        st.subheader("✨ Python Expression Rule")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(
                "Rule Name",
                value="scale_price",
                help="Unique name for this rule (e.g., 'scale_price', 'format_name')",
            )
            source_col = st.text_input(
                "Source Column",
                value="price",
                help="Column to read from",
            )

        with col2:
            target_col = st.text_input(
                "Target Column",
                value="scaled_price",
                help="Column to write to",
            )
            fallback = st.text_input(
                "Fallback Value (if error)",
                value="",
                help="Value if transformation fails",
            )

        st.markdown("#### Expression")
        expression = st.text_area(
            "Python Expression (use 'x' for input value)",
            value="x * 1.1",
            height=100,
            help="""
            Examples:
            - x * 1.1  → Multiply by 1.1
            - round(x, 2)  → Round to 2 decimals
            - str(x).upper()  → Uppercase
            - len(x)  → String length
            
            Safe functions: len, str, int, float, abs, round, min, max, sum
            """,
        )

        st.markdown("#### Modules")
        modules_text = st.text_area(
            "Required Modules (comma-separated)",
            value="",
            height=50,
            help="Available: math, datetime, json (for e.g., 'math.sqrt(x)')",
        )
        modules = [m.strip() for m in modules_text.split(",") if m.strip()] if modules_text else []

        # Validate
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✓ Validate Expression", key="validate_python"):
                expr = PythonExpression(
                    name=name,
                    expression=expression,
                    required_imports=modules,
                )
                is_valid, msg = expr.validate()
                if is_valid:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

        with col2:
            if st.button("🧪 Test Expression", key="test_python"):
                st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA] = {
                    "type": "python",
                    "expression": expression,
                    "modules": modules,
                }
                st.info("👇 Enter test value below")

        # Test interface
        if (
            STTMCustomTransformEditor.KEY_TEST_DATA in st.session_state
            and st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA].get("type") == "python"
        ):
            test_val = st.text_input("Test value (x=)", value="100")
            if st.button("Run Test"):
                try:
                    expr = PythonExpression(
                        name=name,
                        expression=expression,
                        required_imports=modules,
                    )
                    result = expr.evaluate(float(test_val) if test_val.replace(".", "").isdigit() else test_val)
                    st.success(f"Result: {result}")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("✅ Save Python Rule", key="save_python"):
            ruleset = st.session_state[STTMCustomTransformEditor.KEY_RULESET]
            try:
                ruleset.add_python_rule(
                    name=name,
                    source_column=source_col,
                    target_column=target_col,
                    expression=expression,
                    required_imports=modules,
                    fallback_value=fallback or None,
                )
                st.success(f"✅ Saved rule: {name}")
                return {"status": "saved", "name": name}
            except Exception as e:
                st.error(f"❌ Error: {e}")

        return None

    @staticmethod
    def render_regex_rule_editor() -> Optional[Dict[str, Any]]:
        """UI for creating/editing regex rules"""
        st.subheader("🔍 Regex Pattern Rule")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(
                "Rule Name",
                value="extract_phone",
                key="regex_name",
                help="Unique name for this rule",
            )
            source_col = st.text_input(
                "Source Column",
                value="contact",
                key="regex_source",
            )

        with col2:
            target_col = st.text_input(
                "Target Column",
                value="phone",
                key="regex_target",
            )
            fallback = st.text_input(
                "Fallback Value",
                value="",
                key="regex_fallback",
            )

        st.markdown("#### Pattern")
        pattern = st.text_area(
            "Regex Pattern",
            value=r"(\d{3})-(\d{3})-(\d{4})",
            height=80,
            key="regex_pattern",
            help="""
            Examples:
            - (\\d{3})-(\\d{3})-(\\d{4})  → Extract phone: 123-456-7890
            - ([a-z]+)  → Extract word
            - ^[A-Z]+  → Match uppercase start
            """,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            extract_group = st.number_input(
                "Extract Group (0=don't extract)",
                value=0,
                min_value=0,
                max_value=10,
                key="regex_group",
                help="Leave 0 to replace; set to 1, 2, etc. to extract a group",
            )

        with col2:
            replacement = st.text_input(
                "Replacement (if not extracting)",
                value="",
                key="regex_replacement",
                help="Use $1, $2, etc. for group references",
            )

        with col3:
            case_insensitive = st.checkbox("Case Insensitive", value=False, key="regex_ci")

        # Validate
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✓ Validate Pattern", key="validate_regex"):
                try:
                    flags = 2 if case_insensitive else 0  # re.IGNORECASE
                    regex = RegexTransform(
                        name=name,
                        pattern=pattern,
                        replacement=replacement,
                        extract_group=extract_group if extract_group > 0 else None,
                        flags=flags,
                    )
                    st.success("✅ Pattern is valid")
                except Exception as e:
                    st.error(f"❌ Invalid regex: {e}")

        with col2:
            if st.button("🧪 Test Pattern", key="test_regex"):
                st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA] = {
                    "type": "regex",
                    "pattern": pattern,
                    "replacement": replacement,
                    "extract_group": extract_group if extract_group > 0 else None,
                    "case_insensitive": case_insensitive,
                }
                st.info("👇 Enter test value below")

        # Test interface
        if (
            STTMCustomTransformEditor.KEY_TEST_DATA in st.session_state
            and st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA].get("type") == "regex"
        ):
            test_val = st.text_input("Test value", value="Phone: 123-456-7890")
            if st.button("Run Test", key="run_regex_test"):
                try:
                    flags = 2 if case_insensitive else 0
                    regex = RegexTransform(
                        name=name,
                        pattern=pattern,
                        replacement=replacement,
                        extract_group=extract_group if extract_group > 0 else None,
                        flags=flags,
                    )
                    result = regex.transform(test_val)
                    st.success(f"Result: {result}")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("✅ Save Regex Rule", key="save_regex"):
            ruleset = st.session_state[STTMCustomTransformEditor.KEY_RULESET]
            try:
                flags = 2 if case_insensitive else 0
                ruleset.add_regex_rule(
                    name=name,
                    source_column=source_col,
                    target_column=target_col,
                    pattern=pattern,
                    replacement=replacement,
                    extract_group=extract_group if extract_group > 0 else None,
                    fallback_value=fallback or None,
                )
                st.success(f"✅ Saved rule: {name}")
                return {"status": "saved", "name": name}
            except Exception as e:
                st.error(f"❌ Error: {e}")

        return None

    @staticmethod
    def render_lookup_rule_editor() -> Optional[Dict[str, Any]]:
        """UI for creating/editing lookup table rules"""
        st.subheader("📋 Lookup Table Rule")

        col1, col2 = st.columns(2)
        with col1:
            rule_name = st.text_input(
                "Rule Name",
                value="map_state",
                key="lookup_rule_name",
            )
            source_col = st.text_input(
                "Source Column",
                value="state_code",
                key="lookup_source",
            )

        with col2:
            target_col = st.text_input(
                "Target Column",
                value="state_name",
                key="lookup_target",
            )
            fallback = st.text_input(
                "Fallback Value",
                value="Unknown",
                key="lookup_fallback",
            )

        st.markdown("#### Lookup Table")
        table_name = st.text_input(
            "Table Name",
            value="state_codes",
            key="lookup_table_name",
            help="e.g., 'state_codes', 'country_mapping'",
        )

        case_sensitive = st.checkbox(
            "Case Sensitive Matching",
            value=False,
            key="lookup_case_sensitive",
        )

        # Mapping input
        st.markdown("##### Mappings (JSON format)")
        mapping_text = st.text_area(
            "Enter mapping as JSON (key: value pairs)",
            value='{"CA": "California", "NY": "New York", "TX": "Texas"}',
            height=120,
            key="lookup_mapping",
            help="Paste JSON object with key-value pairs",
        )

        if st.button("✓ Validate Mapping", key="validate_lookup"):
            try:
                mapping = json.loads(mapping_text)
                st.success(f"✅ Valid JSON: {len(mapping)} mappings")
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}")

        # Test interface
        if st.button("🧪 Test Lookup", key="test_lookup"):
            st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA] = {
                "type": "lookup",
                "mapping": mapping_text,
            }
            st.info("👇 Enter test value below")

        if (
            STTMCustomTransformEditor.KEY_TEST_DATA in st.session_state
            and st.session_state[STTMCustomTransformEditor.KEY_TEST_DATA].get("type") == "lookup"
        ):
            test_val = st.text_input("Test key", value="CA")
            if st.button("Run Test", key="run_lookup_test"):
                try:
                    mapping = json.loads(mapping_text)
                    table = LookupTable(
                        name=table_name,
                        mapping=mapping,
                        case_sensitive=case_sensitive,
                    )
                    result = table.lookup(test_val)
                    st.success(f"Result: {result}")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("✅ Save Lookup Rule", key="save_lookup"):
            ruleset = st.session_state[STTMCustomTransformEditor.KEY_RULESET]
            try:
                mapping = json.loads(mapping_text)
                table = LookupTable(
                    name=table_name,
                    mapping=mapping,
                    default_value=fallback or None,
                    case_sensitive=case_sensitive,
                )
                ruleset.add_lookup_rule(
                    name=rule_name,
                    source_column=source_col,
                    target_column=target_col,
                    lookup_table=table,
                    fallback_value=fallback or None,
                )
                st.success(f"✅ Saved rule: {rule_name}")
                return {"status": "saved", "name": rule_name}
            except Exception as e:
                st.error(f"❌ Error: {e}")

        return None

    @staticmethod
    def render_rules_list() -> None:
        """Display list of all rules"""
        ruleset = st.session_state.get(STTMCustomTransformEditor.KEY_RULESET)
        if not ruleset:
            return

        rules = ruleset.list_rules()
        if not rules:
            st.info("No rules defined yet")
            return

        st.subheader(f"📝 Rules ({len(rules)})")

        # Display as table
        df_rules = pd.DataFrame(rules)
        st.dataframe(df_rules, use_container_width=True, hide_index=True)

        # Rule management
        st.markdown("#### Manage Rules")
        col1, col2 = st.columns(2)

        with col1:
            rule_to_remove = st.selectbox(
                "Select rule to remove",
                options=[r["name"] for r in rules],
                key="rule_to_remove",
            )
            if st.button("🗑️ Remove Rule", key="remove_rule"):
                ruleset.remove_rule(rule_to_remove)
                st.success(f"Removed: {rule_to_remove}")
                st.rerun()

        with col2:
            rule_to_toggle = st.selectbox(
                "Select rule to toggle",
                options=[r["name"] for r in rules],
                key="rule_to_toggle",
            )
            if st.button("⚡ Toggle Rule", key="toggle_rule"):
                rule = ruleset.get_rule(rule_to_toggle)
                if rule:
                    rule.enabled = not rule.enabled
                    status = "enabled" if rule.enabled else "disabled"
                    st.success(f"Rule {status}: {rule_to_toggle}")
                    st.rerun()

    @staticmethod
    def render_test_on_dataframe(df: pd.DataFrame) -> None:
        """Test rules on sample DataFrame"""
        ruleset = st.session_state.get(STTMCustomTransformEditor.KEY_RULESET)
        if not ruleset or not ruleset.rules:
            st.info("No rules to test")
            return

        st.subheader("🧪 Test on DataFrame")

        # Validation
        if st.button("✓ Validate All Rules"):
            is_valid, issues = ruleset.validate_all()
            if is_valid:
                st.success("✅ All rules are valid")
            else:
                for issue in issues:
                    st.error(f"❌ {issue}")

        # Apply to sample
        if st.button("▶️ Apply Rules to Sample Data"):
            try:
                result_df = ruleset.apply_to_dataframe(df)
                st.success("✅ Rules applied successfully")

                # Show before/after
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Input:**")
                    st.dataframe(df, use_container_width=True)

                with col2:
                    st.markdown("**Output:**")
                    st.dataframe(result_df, use_container_width=True)

            except Exception as e:
                st.error(f"Error applying rules: {e}")

    @staticmethod
    def render_export_import() -> None:
        """Export/import rules as JSON"""
        ruleset = st.session_state.get(STTMCustomTransformEditor.KEY_RULESET)
        if not ruleset:
            return

        st.subheader("💾 Export/Import")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📥 Export Rules as JSON"):
                json_data = json.dumps(ruleset.to_dict(), indent=2, default=str)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=json_data,
                    file_name=f"sttm_rules_{ruleset.run_id}.json",
                    mime="application/json",
                )

        with col2:
            st.markdown("##### Import Rules from JSON")
            uploaded = st.file_uploader(
                "Choose JSON file",
                type="json",
                key="import_rules",
            )
            if uploaded:
                try:
                    data = json.load(uploaded)
                    new_ruleset = CustomTransformRuleSet.from_dict(data)
                    st.session_state[STTMCustomTransformEditor.KEY_RULESET] = new_ruleset
                    st.success("✅ Rules imported successfully")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error importing: {e}")

    @staticmethod
    def render_full_editor(
        sttm_name: str,
        run_id: str,
        sample_df: pd.DataFrame = None,
    ) -> CustomTransformRuleSet:
        """Render complete STTM editor UI"""
        STTMCustomTransformEditor.initialize_session(sttm_name, run_id)

        st.title("🎨 STTM Custom Transformation Editor")
        st.markdown(f"**STTM:** {sttm_name} | **Run ID:** {run_id}")

        # Tabs for different operations
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Python Rules", "Regex Rules", "Lookup Rules", "Manage & Test"]
        )

        with tab1:
            STTMCustomTransformEditor.render_python_rule_editor()

        with tab2:
            STTMCustomTransformEditor.render_regex_rule_editor()

        with tab3:
            STTMCustomTransformEditor.render_lookup_rule_editor()

        with tab4:
            st.markdown("### 📋 View All Rules")
            STTMCustomTransformEditor.render_rules_list()

            if sample_df is not None:
                st.markdown("---")
                STTMCustomTransformEditor.render_test_on_dataframe(sample_df)

            st.markdown("---")
            STTMCustomTransformEditor.render_export_import()

        return st.session_state[STTMCustomTransformEditor.KEY_RULESET]
