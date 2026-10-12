"""
Chat engine for natural language queries on Gold layer data.

Converts user questions to SQL, executes them, and maintains conversation context.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import duckdb

from core.config import GOLD_DIR, LLM_PROVIDER
from core.observability import AgentTrace


def _make_llm():
    """Create LLM instance based on configured provider."""
    from core.config import (
        GOOGLE_API_KEY, GEMINI_MODEL,
        GROQ_API_KEY, GROQ_MODEL,
        OPENAI_API_KEY, OPENAI_MODEL,
        GITHUB_TOKEN, GITHUB_MODEL, GITHUB_BASE_URL,
    )
    
    if LLM_PROVIDER == "google" and GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            api_key=GOOGLE_API_KEY,
            temperature=0,
        )
    elif LLM_PROVIDER == "groq" and GROQ_API_KEY:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0,
            reasoning_format="hidden",
        )
    elif LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
    elif LLM_PROVIDER == "github" and GITHUB_TOKEN:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=GITHUB_MODEL,
            api_key=GITHUB_TOKEN,
            base_url=GITHUB_BASE_URL,
            temperature=0,
        )
    
    raise ValueError(f"No valid LLM configured (provider: {LLM_PROVIDER})")


class ChatEngine:
    """Generate SQL from natural language questions and execute against Gold tables."""
    
    def __init__(self, parquet_file: Path, run_id: str):
        """
        Initialize chat engine with Gold layer parquet file.
        
        Args:
            parquet_file: Path to gold layer parquet file
            run_id: Run ID for tracing
        """
        self.parquet_file = Path(parquet_file)
        self.run_id = run_id
        self.llm = _make_llm()
        self.conversation_history = []
        self.schema_cache = None
        self.trace = AgentTrace("ChatEngine", run_id)
        self.trace.set_input(
            parquet_file=str(parquet_file),
            run_id=run_id
        )
    
    def _get_schema(self) -> str:
        """Get table schema from parquet file."""
        if self.schema_cache:
            return self.schema_cache
        
        try:
            conn = duckdb.connect(":memory:")
            conn.execute(f"CREATE TABLE data AS SELECT * FROM '{str(self.parquet_file)}'")
            
            # Get column info
            result = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'data'"
            ).fetchall()
            
            schema = "Table 'data' columns:\n"
            for col_name, col_type in result:
                schema += f"  - {col_name} ({col_type})\n"
            
            # Get sample rows
            sample = conn.execute("SELECT * FROM data LIMIT 3").fetchall()
            schema += f"\nSample data (first 3 rows):\n{sample}"
            
            conn.close()
            self.schema_cache = schema
            return schema
        except Exception as e:
            error_msg = f"Failed to get schema: {str(e)}"
            self.trace.set_output(error=error_msg)
            raise ValueError(error_msg)
    
    def _generate_sql(self, question: str) -> str:
        """
        Convert natural language question to SQL.
        
        Args:
            question: Natural language question
            
        Returns:
            SQL query string
        """
        schema = self._get_schema()
        
        system_prompt = f"""You are a SQL expert. Convert the user's question to a valid SQL query.

{schema}

Rules:
1. Return ONLY the SQL query, no explanation
2. Use DuckDB SQL syntax
3. Always use column names exactly as shown above
4. For time-based questions, handle dates carefully
5. Use LIMIT 100 for result sets unless specified otherwise
6. If the question is ambiguous, make reasonable assumptions

Important: Return ONLY the SQL query, wrapped in triple backticks (```sql ... ```)."""
        
        self.conversation_history.append(("user", question))
        
        response = self.llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        
        sql_text = response.content.strip()
        
        # Extract SQL from backticks if present
        if "```sql" in sql_text:
            sql_text = sql_text.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql_text:
            sql_text = sql_text.split("```")[1].split("```")[0].strip()
        
        self.trace.set_plan(f"Generated SQL for question: {question}")
        
        return sql_text
    
    def _validate_sql(self, sql_query: str) -> bool:
        """
        Validate SQL is safe (no destructive operations).
        
        Args:
            sql_query: SQL query to validate
            
        Returns:
            True if safe, False otherwise
        """
        dangerous_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER"]
        sql_upper = sql_query.upper().strip()
        
        for keyword in dangerous_keywords:
            if sql_upper.startswith(keyword):
                return False
        
        return True
    
    def query(self, question: str, max_rows: int = 100) -> dict:
        """
        Answer natural language question about Gold data.
        
        Args:
            question: Natural language question
            max_rows: Maximum rows to return
            
        Returns:
            Dictionary with:
                - success (bool)
                - sql (str) - the generated SQL
                - results (list) - query results
                - columns (list) - column names
                - error (str) - error message if failed
                - message (str) - human-readable summary
        """
        try:
            # Generate SQL
            sql_query = self._generate_sql(question)
            
            # Validate SQL
            if not self._validate_sql(sql_query):
                error_msg = "Query rejected: destructive operations not allowed"
                self.conversation_history.append(("assistant", error_msg))
                return {
                    "success": False,
                    "sql": sql_query,
                    "error": error_msg,
                    "message": "❌ " + error_msg,
                    "results": [],
                    "columns": [],
                }
            
            # Execute query
            conn = duckdb.connect(":memory:")
            conn.execute(f"CREATE TABLE data AS SELECT * FROM '{str(self.parquet_file)}'")
            
            result_set = conn.execute(sql_query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            # Limit results
            if len(result_set) > max_rows:
                result_set = result_set[:max_rows]
                truncated = True
            else:
                truncated = False
            
            conn.close()
            
            # Format response
            results = [dict(zip(columns, row)) for row in result_set]
            
            message = f"✅ Retrieved {len(results)} rows"
            if truncated:
                message += f" (showing first {max_rows})"
            
            self.conversation_history.append(("assistant", json.dumps(results[:3])))  # Store sample
            
            self.trace.set_output(
                rows_returned=len(results),
                sql_executed=sql_query
            )
            
            return {
                "success": True,
                "sql": sql_query,
                "results": results,
                "columns": columns,
                "error": None,
                "message": message,
                "row_count": len(results),
                "truncated": truncated,
            }
        
        except Exception as e:
            error_msg = str(e)
            self.conversation_history.append(("assistant", f"Error: {error_msg}"))
            
            return {
                "success": False,
                "sql": None,
                "error": error_msg,
                "message": f"❌ Query failed: {error_msg}",
                "results": [],
                "columns": [],
            }
    
    def get_conversation_history(self) -> list:
        """Get full conversation history."""
        return self.conversation_history.copy()
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_sample_questions(self) -> list:
        """Get example questions user might ask."""
        return [
            "What is the total revenue by region?",
            "Show me the top 5 products by sales",
            "What was the trend over the last 6 months?",
            "Compare performance between regions",
            "Which product had the highest profit margin?",
            "How many unique customers do we have?",
            "What is the average order value?",
            "Show me sales by category",
        ]
    
    def complete(self):
        """Save trace and mark complete."""
        self.trace.complete(status="success")
