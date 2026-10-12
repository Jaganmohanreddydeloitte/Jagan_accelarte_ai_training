"""
Streamlit UI component for interactive chat about Gold layer data.

Provides conversation interface with SQL generation and result display.
"""

import streamlit as st
import pandas as pd
from pathlib import Path

from core.chat_engine import ChatEngine


def render_chat_interface(gold_file: Path, run_id: str):
    """
    Render interactive chat interface for data exploration.
    
    Args:
        gold_file: Path to gold layer parquet file
        run_id: Run ID for tracking
    """
    st.subheader("💬 Ask Questions About Your Data")
    st.caption("Ask follow-up questions in natural language. The AI will generate SQL to answer them.")
    
    # Initialize chat engine in session state
    if "chat_engine" not in st.session_state:
        st.session_state.chat_engine = ChatEngine(gold_file, run_id)
    
    engine = st.session_state.chat_engine
    
    # Create two columns: chat history + input on left, suggestions on right
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.write("**Example Questions:**")
        for i, q in enumerate(engine.get_sample_questions()[:4]):
            if st.button(q, key=f"sample_{i}", use_container_width=True):
                st.session_state.user_input = q
    
    with col1:
        # Display conversation history
        chat_container = st.container()
        
        with chat_container:
            st.write("**Conversation:**")
            
            history = engine.get_conversation_history()
            
            if not history:
                st.info("💡 Start by asking a question about your data!")
            else:
                for speaker, message in history:
                    if speaker == "user":
                        with st.chat_message("user", avatar="👤"):
                            st.write(message)
                    else:
                        with st.chat_message("assistant", avatar="🤖"):
                            st.write(message)
        
        # Input section
        st.divider()
        
        input_col, button_col = st.columns([4, 1])
        
        with input_col:
            user_question = st.text_input(
                "Ask a question:",
                placeholder="e.g., What was the top selling product?",
                key="chat_input",
                label_visibility="collapsed"
            )
        
        with button_col:
            submit_button = st.button("Send", key="send_button", use_container_width=True)
        
        # Process question
        if submit_button and user_question:
            with st.spinner("Generating SQL and executing query..."):
                result = engine.query(user_question)
            
            # Display result
            if result["success"]:
                with st.chat_message("assistant", avatar="🤖"):
                    st.success(result["message"])
                    
                    # Show SQL
                    with st.expander("📝 View SQL Query", expanded=False):
                        st.code(result["sql"], language="sql")
                    
                    # Show results table
                    if result["results"]:
                        st.write("**Results:**")
                        df = pd.DataFrame(result["results"])
                        st.dataframe(df, use_container_width=True)
                        
                        # Offer to visualize
                        if len(result["columns"]) > 0:
                            numeric_cols = [
                                col for col in result["columns"]
                                if isinstance(result["results"][0].get(col), (int, float))
                            ]
                            
                            if numeric_cols and len(result["results"]) > 1:
                                viz_type = st.selectbox(
                                    "📊 Visualize as:",
                                    ["Table", "Bar Chart", "Line Chart", "Pie Chart"],
                                    key=f"viz_{result['row_count']}"
                                )
                                
                                if viz_type == "Bar Chart":
                                    st.bar_chart(df, x=result["columns"][0], y=numeric_cols[0])
                                elif viz_type == "Line Chart" and len(numeric_cols) > 0:
                                    st.line_chart(df, y=numeric_cols[0])
                                elif viz_type == "Pie Chart" and len(numeric_cols) > 0:
                                    st.pie_chart(df.set_index(result["columns"][0])[numeric_cols[0]])
                    
                    else:
                        st.info("No results found matching your query.")
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.error(result["message"])
                    if result["error"]:
                        st.code(result["error"], language="text")
            
            # Clear input
            st.rerun()
        
        # Clear history button
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("🗑️ Clear Chat", key="clear_chat"):
                engine.clear_history()
                st.rerun()
        
        with col2:
            if st.button("📋 Export", key="export_chat"):
                history_json = "\n".join([
                    f"{speaker}: {msg}"
                    for speaker, msg in engine.get_conversation_history()
                ])
                st.download_button(
                    label="Download Chat",
                    data=history_json,
                    file_name=f"chat_history_{run_id}.txt",
                    mime="text/plain"
                )


def render_chat_widget(gold_file: Path, run_id: str):
    """
    Render minimal chat widget (for sidebar or compact view).
    
    Args:
        gold_file: Path to gold layer parquet file
        run_id: Run ID for tracking
    """
    if "chat_engine" not in st.session_state:
        st.session_state.chat_engine = ChatEngine(gold_file, run_id)
    
    engine = st.session_state.chat_engine
    
    st.subheader("💬 Quick Questions")
    
    user_question = st.text_input(
        "Ask about your data:",
        placeholder="e.g., Top 5 products?",
        key="widget_input"
    )
    
    if user_question and st.button("🔍 Ask"):
        with st.spinner("Processing..."):
            result = engine.query(user_question)
        
        if result["success"]:
            st.success(result["message"])
            if result["results"]:
                st.dataframe(
                    pd.DataFrame(result["results"]),
                    use_container_width=True
                )
        else:
            st.error(result["message"])
