"""
Integration guide: Using the ChatEngine in different scenarios.

This file shows code examples for common use cases.
"""

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Basic Usage in Streamlit App
# ─────────────────────────────────────────────────────────────────────────────

"""
The chat interface is already integrated in the report phase.
Just ensure the imports are in place:
"""

# In app/streamlit_app.py:
from core.chat_ui import render_chat_interface

# In report phase:
gold_files = st.session_state.pipeline_state.get("gold_output_paths", [])
if gold_files:
    render_chat_interface(gold_files[0], run_id)


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Using ChatEngine Programmatically
# ─────────────────────────────────────────────────────────────────────────────

from pathlib import Path
from core.chat_engine import ChatEngine

# Initialize with gold layer file
gold_file = Path("data/gold_layer/products.parquet")
run_id = "run_20240815_123456"

engine = ChatEngine(gold_file, run_id)

# Ask a question
result = engine.query("What is the top selling product?")

# Check if successful
if result["success"]:
    print(f"✅ Query succeeded")
    print(f"SQL: {result['sql']}")
    print(f"Rows: {result['row_count']}")
    
    # Process results
    for row in result["results"]:
        print(f"  Product: {row['product_name']}, Sales: {row['total_sales']}")
else:
    print(f"❌ Error: {result['error']}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Multi-Turn Conversation
# ─────────────────────────────────────────────────────────────────────────────

engine = ChatEngine(gold_file, run_id)

# Question 1
result1 = engine.query("What are the top 5 products by revenue?")
if result1["success"]:
    print("Top 5 products:", [r["product_name"] for r in result1["results"]])

# Question 2 (follow-up)
result2 = engine.query("What is the profit margin for each of those products?")
if result2["success"]:
    for row in result2["results"]:
        print(f"{row['product_name']}: {row['profit_margin']}%")

# Get full conversation history
history = engine.get_conversation_history()
for speaker, message in history:
    print(f"{speaker.upper()}: {message}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Batch Processing Multiple Questions
# ─────────────────────────────────────────────────────────────────────────────

questions = [
    "How many unique customers do we have?",
    "What is the average order value?",
    "What region has the highest sales?",
    "Top 3 products by profit?",
]

engine = ChatEngine(gold_file, run_id)
results = []

for question in questions:
    result = engine.query(question)
    results.append({
        "question": question,
        "success": result["success"],
        "row_count": result.get("row_count", 0),
        "error": result.get("error")
    })
    print(f"Q: {question}")
    print(f"   Status: {'✅ OK' if result['success'] else '❌ ERROR'}")
    print(f"   Rows: {result.get('row_count', 'N/A')}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Custom Visualization After Query
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import matplotlib.pyplot as plt

engine = ChatEngine(gold_file, run_id)

# Execute query
result = engine.query("Show me sales by month for 2024")

if result["success"]:
    # Convert to DataFrame
    df = pd.DataFrame(result["results"])
    
    # Create custom visualization
    plt.figure(figsize=(12, 6))
    plt.plot(df["month"], df["sales"], marker='o')
    plt.title("Monthly Sales Trend 2024")
    plt.xlabel("Month")
    plt.ylabel("Sales ($)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("sales_trend.png")
    print("Saved sales_trend.png")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 6: Error Handling and Validation
# ─────────────────────────────────────────────────────────────────────────────

engine = ChatEngine(gold_file, run_id)

# Try a potentially dangerous query
result = engine.query("DROP TABLE data")

if not result["success"]:
    print(f"Query blocked (safe): {result['error']}")

# Try an ambiguous question
result = engine.query("Tell me about products")

if result["success"]:
    print(f"Generated SQL: {result['sql']}")
    print(f"Results: {len(result['results'])} rows")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 7: Exporting Query Results
# ─────────────────────────────────────────────────────────────────────────────

import json
import csv

engine = ChatEngine(gold_file, run_id)
result = engine.query("Top 10 customers by lifetime value")

if result["success"]:
    # Export as JSON
    with open("top_customers.json", "w") as f:
        json.dump(result["results"], f, indent=2)
    
    # Export as CSV
    df = pd.DataFrame(result["results"])
    df.to_csv("top_customers.csv", index=False)
    
    # Print summary
    print(f"Exported {len(result['results'])} rows")
    print("Files: top_customers.json, top_customers.csv")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 8: Sample Questions Generation
# ─────────────────────────────────────────────────────────────────────────────

engine = ChatEngine(gold_file, run_id)

# Get suggested questions
sample_questions = engine.get_sample_questions()

print("Suggested questions:")
for i, q in enumerate(sample_questions, 1):
    print(f"{i}. {q}")

# You can extend this with custom questions based on schema
# e.g., if "date" column exists, add time-based questions


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 9: Caching and Session Management
# ─────────────────────────────────────────────────────────────────────────────

engine = ChatEngine(gold_file, run_id)

# First query - extracts schema (slow)
result1 = engine.query("Count of customers")  # ~5 seconds

# Subsequent queries - uses cached schema (fast)
result2 = engine.query("Top products")  # ~2 seconds
result3 = engine.query("Sales by region")  # ~2 seconds

# Clear history for next conversation
engine.clear_history()
print("Chat history cleared")

# Schema cache is still active for performance
# To clear schema cache too:
engine.schema_cache = None
next_query = engine.query("New question")  # Will re-extract schema


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 10: Integration with Existing Audit System
# ─────────────────────────────────────────────────────────────────────────────

from core.audit import AuditLogger

run_id = "run_20240815_123456"
audit = AuditLogger(run_id)
engine = ChatEngine(gold_file, run_id)

# Log the chat session
audit.log("chat_engine", "session_started", 
          gold_file=str(gold_file))

# Ask questions
result = engine.query("What is the total revenue?")

if result["success"]:
    # Log successful query
    audit.log("chat_engine", "query_success",
              question="What is the total revenue?",
              sql=result["sql"],
              row_count=result["row_count"])
else:
    # Log failed query
    audit.log("chat_engine", "query_failed",
              question="What is the total revenue?",
              error=result["error"])

# Get audit trail
logs = audit.get_logs()
print(f"Total audit logs: {len(logs)}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 11: Using Different LLM Providers
# ─────────────────────────────────────────────────────────────────────────────

"""
The ChatEngine automatically uses the configured LLM provider.
Set your preferred provider in .env:

LLM_PROVIDER=groq  # Use Groq
LLM_PROVIDER=openai  # Use OpenAI
LLM_PROVIDER=google  # Use Google
LLM_PROVIDER=github  # Use GitHub Models

Each provider has its own API key:
GROQ_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
GITHUB_TOKEN=...

The ChatEngine will auto-detect and use the first available provider
in this order: github > openai > groq > google
"""

# To verify which provider is being used:
from core.config import LLM_PROVIDER
print(f"Using LLM provider: {LLM_PROVIDER}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 12: Advanced - Custom SQL Generation
# ─────────────────────────────────────────────────────────────────────────────

"""
You can subclass ChatEngine to customize SQL generation:
"""

class CustomChatEngine(ChatEngine):
    def _generate_sql(self, question: str) -> str:
        # Add custom logic here
        # e.g., translate business terms to column names
        
        business_terms = {
            "revenue": "total_sales",
            "profit": "net_profit",
            "customers": "customer_count",
        }
        
        # Replace business terms
        for term, column in business_terms.items():
            question = question.replace(term, column)
        
        # Call parent implementation
        return super()._generate_sql(question)


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 13: Testing ChatEngine
# ─────────────────────────────────────────────────────────────────────────────

"""
Unit test example:
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path

class TestChatEngine(unittest.TestCase):
    def setUp(self):
        self.gold_file = Path("test_data/gold.parquet")
        self.run_id = "test_run_123"
        self.engine = ChatEngine(self.gold_file, self.run_id)
    
    def test_schema_extraction(self):
        # Test that schema is extracted correctly
        schema = self.engine._get_schema()
        self.assertIn("columns:", schema)
        self.assertIn("data_type", schema)
    
    def test_sql_validation_blocks_drop(self):
        # Test that DROP is blocked
        is_valid = self.engine._validate_sql("DROP TABLE data")
        self.assertFalse(is_valid)
    
    def test_sql_validation_allows_select(self):
        # Test that SELECT is allowed
        is_valid = self.engine._validate_sql("SELECT * FROM data LIMIT 5")
        self.assertTrue(is_valid)
    
    def test_query_returns_results(self):
        # Test that a query returns results
        result = self.engine.query("SELECT * FROM data LIMIT 1")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["results"]), 0)


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 14: Monitoring Query Performance
# ─────────────────────────────────────────────────────────────────────────────

import time

engine = ChatEngine(gold_file, run_id)

questions = [
    "Total revenue?",
    "Top 10 products?",
    "Average order value by region?",
]

print("Query Performance Analysis:")
print("=" * 50)

for question in questions:
    start = time.time()
    result = engine.query(question)
    duration = time.time() - start
    
    status = "✅" if result["success"] else "❌"
    print(f"{status} Q: {question}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Rows: {result.get('row_count', 'N/A')}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 15: API Endpoint (Future Enhancement)
# ─────────────────────────────────────────────────────────────────────────────

"""
Planned: REST API endpoint for chat

@app.post("/api/chat/{run_id}")
def chat(run_id: str, question: str, gold_file: str):
    engine = ChatEngine(Path(gold_file), run_id)
    result = engine.query(question)
    return result

Usage:
curl -X POST "http://localhost:8000/api/chat/run_123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Top 5 products?"}'
"""
