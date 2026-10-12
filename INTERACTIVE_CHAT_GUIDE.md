# Interactive Chat for Gold Layer Data

## What It Does (3 Sentences)

The Interactive Chat feature allows users to ask natural language questions about their Gold layer data after the report is generated, which are automatically converted to SQL queries and executed in real-time. Questions like "What was the top selling product?" or "Show me the trend over the last 3 months" are parsed by an LLM, converted to SQL, and results are displayed with optional visualizations. The chat maintains conversation history, validates queries for safety, and displays results inline with charts, tables, and export capabilities.

---

## Overview

After generating a report, users can interactively explore the Gold layer data using natural language questions. The system:

1. **Accepts Natural Language Questions** - Users ask questions like "Show me top 5 products"
2. **Generates SQL Automatically** - LLM converts questions to SQL queries
3. **Validates for Safety** - Prevents destructive operations (DROP, DELETE, etc.)
4. **Executes Queries** - Runs SQL against the Gold layer parquet file
5. **Displays Results** - Shows tables, charts, and options for visualization
6. **Maintains History** - Keeps conversation context for follow-up questions
7. **Allows Export** - Users can download chat history

---

## Key Features

### ✨ Natural Language Processing
- Ask questions in plain English
- LLM understands business concepts
- Intelligent SQL generation

### 🔒 Safety & Validation
- Blocks destructive operations
- Column name validation
- Schema context awareness

### 📊 Rich Visualizations
- Automatic table display
- Bar charts for categorical data
- Line charts for time series
- Pie charts for distributions

### 💬 Conversation Management
- Full conversation history
- Context-aware follow-up questions
- Clear chat to start fresh
- Export chat as text file

### ⚡ Performance
- Schema caching for fast generation
- Efficient DuckDB execution
- Result pagination (limit 100)

---

## Architecture

### Data Flow

```
User Question
    ↓
[LangChain LLM]
    ↓
SQL Generation (with schema context)
    ↓
[SQL Validator]
    ↓
[DuckDB] ← Gold Layer Parquet File
    ↓
Results (rows + columns)
    ↓
[Streamlit UI] → Table, Charts, Export
```

### Components

**core/chat_engine.py:**
- `ChatEngine` class - Main orchestrator
- `_generate_sql()` - LLM-based SQL generation
- `_validate_sql()` - Security validation
- `query()` - Execute and return results
- Conversation history management

**core/chat_ui.py:**
- `render_chat_interface()` - Full chat UI
- `render_chat_widget()` - Compact version
- Chat message display
- Result visualization
- Export functionality

**app/streamlit_app.py:**
- Integration in report phase
- Session state management
- Display after report

---

## How to Use

### 1. After Report Generation

Once your report is displayed, scroll down to see the chat interface:

```
📊 Phase 5: Executive Report
[Report HTML Display]
━━━━━━━━━━━━━━━━━━━━━━
💬 Ask Questions About Your Data
[Chat Interface Appears Here]
```

### 2. Ask a Question

Click "Example Questions" for suggestions or type your own:

```
"What was the top selling product?"
"Show me sales by region"
"Compare East vs West performance"
"What is the average order value?"
```

### 3. Review Generated SQL

After asking, the system shows:
- **✅ Query Status** - Success or error
- **📝 SQL Query** - View the generated SQL (expandable)
- **Results Table** - All returned rows

### 4. Visualize Results

For numeric data, choose visualization:
- **Bar Chart** - Categories vs numbers
- **Line Chart** - Time series data
- **Pie Chart** - Proportions/distributions

### 5. Export Chat

Click **📋 Export** to download chat history as text file.

### 6. Follow-up Questions

Ask multiple questions - context is maintained:
```
Q: "Top 5 products?"
A: [Results with product names]

Q: "Show me the profit margin for each"
A: [New query with products from previous answer]

Q: "Which region has the highest margin?"
A: [Follow-up on previous results]
```

---

## Example Questions

### Aggregation
- "What is the total revenue?"
- "How many unique customers?"
- "Average order value by region?"

### Ranking
- "Top 10 products by sales?"
- "Bottom 5 performing SKUs?"
- "Highest profit margins?"

### Filtering
- "Sales over $10,000?"
- "Customers from East region?"
- "Orders in last 30 days?"

### Comparison
- "East vs West sales?"
- "This quarter vs last quarter?"
- "Product A vs Product B?"

### Trends
- "Monthly sales trend?"
- "Growth rate by quarter?"
- "Year-over-year comparison?"

---

## Technical Details

### SQL Generation Prompt

```
System: You are a SQL expert. Convert the user's question to a valid SQL query.

[Schema Information]
- Table name: 'data'
- Columns: [list with data types]
- Sample rows: [first 3 rows]

Rules:
1. Return ONLY the SQL query, no explanation
2. Use DuckDB SQL syntax
3. Use exact column names
4. Handle dates carefully
5. Use LIMIT 100 unless specified
6. Make reasonable assumptions if ambiguous

Return ONLY SQL wrapped in ```sql ... ```
```

### SQL Validation

Blocked operations:
```python
dangerous_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER"]
```

All queries must:
1. Start with SELECT (read-only)
2. Contain no destructive operations
3. Use exact column names from schema
4. Return valid results

### Schema Caching

First query: Reads parquet, extracts schema (5-10 sec)
Subsequent queries: Uses cached schema (instant)

Cache is per-session, cleared when chat resets.

### Result Pagination

- Default limit: 100 rows
- Rows truncated: Shows "Showing first 100"
- No row limit override: Users cannot request LIMIT 1000000
- Performance: O(1) display time regardless of result size

---

## Integration Points

### In Streamlit App

```python
from core.chat_ui import render_chat_interface

# In report phase
gold_files = pipeline_state.get("gold_output_paths", [])
if gold_files:
    render_chat_interface(gold_files[0], run_id)
```

### With Existing Components

- **Agents**: Chat engine is independent, doesn't require changes
- **API**: Can be exposed via FastAPI endpoint (future enhancement)
- **Caching**: Works with existing cache system for repeated queries
- **Audit**: Queries logged in conversation history (not audit trail yet)

---

## Error Handling

### Common Errors

**Error: "Failed to get schema"**
- Cause: Parquet file corrupted
- Fix: Regenerate Gold layer

**Error: "Query rejected: destructive operations"**
- Cause: User tried DROP/DELETE/etc
- Fix: Only SELECT queries allowed

**Error: "Invalid column name: [column]"**
- Cause: Question references non-existent column
- Fix: Review schema, ask about available columns

**Error: "Query failed: [specific error]"**
- Cause: SQL syntax error or DuckDB issue
- Fix: Rephrase question more clearly

### Debug Output

To debug, check:
1. **Generated SQL** - Click "View SQL Query" expander
2. **Error Message** - Full DuckDB error is shown
3. **Schema** - Ask "What columns are available?"

---

## Performance Considerations

### Schema Extraction: 5-10 seconds
- Reads entire parquet file
- Extracts column metadata
- Cached after first use

### SQL Generation: 1-3 seconds
- LLM API call
- Depends on LLM provider

### Query Execution: <1 second (usually)
- DuckDB in-memory query
- Most queries return in 100-500ms
- Large aggregations may take 1-2 seconds

### Total Per Query: 2-5 seconds

### Optimization Tips
- Ask focused questions (fewer columns)
- Use time ranges for large datasets
- Ask for top N instead of all rows

---

## Security

### SQL Injection Prevention
- No string interpolation
- LLM generates SQL (not templating)
- Validator checks query type

### Data Access
- Read-only access only
- No schema modification
- No data modification

### Privacy
- Conversation history stored in session
- Chat cleared when user restarts workflow
- No external logging of queries

---

## Future Enhancements

### Planned
- [ ] Follow-up context awareness (reference previous results)
- [ ] Chart recommendations (auto-suggest visualization)
- [ ] Query optimization (suggest better queries)
- [ ] Multi-table queries (join across Gold tables)
- [ ] Saved queries (bookmark common questions)

### Possible
- [ ] REST API endpoint for chat
- [ ] Conversation persistence (save chat history)
- [ ] Export results as CSV/JSON
- [ ] Custom chart templates
- [ ] Query performance metrics

---

## Configuration

### Default Settings

```python
# core/chat_engine.py
MAX_ROWS = 100  # Result limit
SCHEMA_CACHE_TTL = "session"  # Clear on restart

# Temperature = 0 (deterministic)
# No creative text generation
```

### Customization

To change max rows:

```python
result = engine.query(question, max_rows=500)
```

To clear schema cache manually:

```python
engine.schema_cache = None
```

---

## Testing

### Unit Tests

```python
# tests/test_chat_engine.py
- test_schema_extraction()
- test_sql_generation()
- test_sql_validation()
- test_query_execution()
- test_result_formatting()
```

### Manual Testing

1. **Test Basic Query**
   - Q: "How many rows?"
   - Expected: Returns total count

2. **Test Filtering**
   - Q: "Top 5 products?"
   - Expected: 5 rows ordered by product

3. **Test Aggregation**
   - Q: "Total sales by region?"
   - Expected: Grouped results

4. **Test Safety**
   - Q: "DROP TABLE data"
   - Expected: "Query rejected"

5. **Test Follow-up**
   - Q: "What columns are available?"
   - A: [Lists columns]
   - Q: "What is the [column] range?"
   - Expected: Context-aware response

---

## Troubleshooting

### Chat Not Appearing

**Symptom**: No chat interface after report

**Causes**:
1. Gold layer files missing
2. Chat UI not imported
3. Parquet file corrupted

**Fix**:
```python
# In streamlit_app.py
gold_files = pipeline_state.get("gold_output_paths", [])
print(f"Gold files: {gold_files}")  # Debug

if not gold_files:
    st.error("No Gold layer available")
```

### Slow Query Generation

**Symptom**: Takes 5+ seconds to generate SQL

**Causes**:
1. Slow LLM API
2. Large parquet file (schema extraction)
3. Network latency

**Fix**:
- Use faster LLM (GitHub Models > Groq)
- Pre-profile with smaller datasets
- Check network connection

### "Invalid column name" Error

**Symptom**: Question references column that doesn't exist

**Causes**:
1. Column name changed
2. Wrong dataset profile
3. Question has typo

**Fix**:
- Ask "What columns are available?"
- Check column names in schema expander
- Ask more specific question

### LLM Returns Invalid SQL

**Symptom**: Generated SQL has syntax errors

**Causes**:
1. LLM misunderstood question
2. Schema context incomplete
3. LLM configuration issue

**Fix**:
- Check Generated SQL expander
- Rephrase question more clearly
- Check `reasoning_format="hidden"` for Groq

---

## FAQ

**Q: Can I modify or delete data?**
A: No. Only SELECT queries (read-only) are allowed. Destructive operations are blocked.

**Q: Can I join tables?**
A: Currently only single table queries. Multi-table support planned for future.

**Q: Does chat history persist?**
A: No. History is cleared when you restart the workflow or close the browser.

**Q: How much data can I query?**
A: Limited to parquet file size. Results capped at 100 rows for display.

**Q: Can I export results?**
A: Yes, download as CSV by clicking table (if available in future) or export chat.

**Q: What SQL dialect is used?**
A: DuckDB SQL. Mostly compatible with standard SQL but some functions differ.

**Q: Can I run complex queries?**
A: Yes, but phrasing matters. "Show me sales by region ordered by total descending" is better than "order by".

**Q: Does it understand context?**
A: Partially. It remembers previous questions in conversation but doesn't use results in queries yet.

---

## See Also

- `core/chat_engine.py` - Implementation details
- `core/chat_ui.py` - UI components
- `app/streamlit_app.py` - Integration point
- `agents/reporter.py` - Gold layer generation
