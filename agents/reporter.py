"""
Reporter agent — generates business reports from Gold tables using SQL queries and Plotly charts.
"""

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from langchain_core.tools import tool

from core.audit import AuditLogger
from core.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GOOGLE_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REPORTS_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
REPORTER_AGENT_PROMPT = """You are a Business Intelligence Analyst generating reports from data.

Your task: analyze Gold tables and generate a comprehensive business report.

Follow this sequence:
1. Call inspect_gold_tables_tool to see available tables and schemas
2. Call load_gold_data_tool to load data into the query engine
3. Call execute_query_tool with SQL queries to answer the business question
4. Create chart specifications for visualizations (bar, line, pie, scatter)
5. Call submit_analysis_tool with a JSON containing: direct_answer, charts, detailed_analysis

Return analysis with actionable insights, visualizations, and SQL approach.
"""


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _inspect_gold_tables(gold_files: list[str]) -> dict:
    """Preview Gold table schemas and sample rows."""
    result = {}
    for fpath in gold_files:
        try:
            df = pd.read_parquet(fpath)
            table_name = Path(fpath).stem
            result[table_name] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample_rows": df.head(3).to_dict(orient="records"),
            }
        except Exception as e:
            result[fpath] = {"error": str(e)}
    return result


def generate_chart_from_spec(df: pd.DataFrame, chart_spec: dict, chart_id: str) -> str:
    """Generate Plotly chart HTML from specification."""
    chart_type = chart_spec.get("type", "bar").lower()
    title = chart_spec.get("title", "Chart")
    x_column = chart_spec.get("x_column")
    y_column = chart_spec.get("y_column")
    z_column = chart_spec.get("z_column")

    fig = None

    try:
        if chart_type == "bar":
            fig = go.Figure(
                data=go.Bar(x=df[x_column], y=df[y_column], name=y_column)
            )
        elif chart_type == "line":
            fig = go.Figure(
                data=go.Scatter(x=df[x_column], y=df[y_column], mode="lines", name=y_column)
            )
        elif chart_type == "pie":
            fig = go.Figure(
                data=go.Pie(labels=df[x_column], values=df[y_column])
            )
        elif chart_type == "scatter":
            fig = go.Figure(
                data=go.Scatter(x=df[x_column], y=df[y_column], mode="markers", name=y_column)
            )
        else:
            fig = go.Figure(
                data=go.Bar(x=df[x_column], y=df[y_column], name=y_column)
            )

        fig.update_layout(
            title=title,
            xaxis_title=x_column,
            yaxis_title=y_column if y_column != x_column else "",
            height=400,
            template="plotly_white",
        )

        return fig.to_html(include_plotlyjs="cdn", div_id=chart_id)

    except Exception as e:
        return f"<p>Error generating chart: {e}</p>"


# ─── LLM Factory ────────────────────────────────────────────────────────────

def _make_llm():
    """Create LLM based on LLM_PROVIDER setting."""
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0.5,
            reasoning_format="hidden",
            reasoning_effort="low",
        )
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            temperature=0.5,
        )
    elif LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            api_key=GOOGLE_API_KEY,
            model=GEMINI_MODEL,
            temperature=0.5,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


# ─── Tool Factory ───────────────────────────────────────────────────────────

def _make_reporter_tools(gold_files: list[str], run_id: str):
    """Create tools for the reporter agent."""
    scratchpad = {}
    db_connection = {"conn": None}

    @tool
    def inspect_gold_tables_tool() -> str:
        """Inspect Gold table schemas and sample data."""
        result = _inspect_gold_tables(gold_files)
        logger = AuditLogger(run_id)
        logger.log("reporter", "inspect_gold_tables", result=result)
        return json.dumps(result, indent=2, default=str)

    @tool
    def load_gold_data_tool() -> str:
        """Load Gold Parquet files into DuckDB."""
        try:
            conn = duckdb.connect(":memory:")
            catalog = {}

            for fpath in gold_files:
                df = pd.read_parquet(fpath)
                table_name = Path(fpath).stem
                conn.register(table_name, df)
                catalog[table_name] = {
                    "shape": df.shape,
                    "columns": list(df.columns),
                }

            db_connection["conn"] = conn
            logger = AuditLogger(run_id)
            logger.log("reporter", "load_gold_data", catalog=catalog)
            return json.dumps(catalog, indent=2, default=str)

        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("reporter", "load_gold_data_error", error=str(e))
            raise

    @tool
    def execute_query_tool(sql_query: str) -> str:
        """Execute SQL query against loaded Gold tables."""
        try:
            if not db_connection["conn"]:
                raise ValueError("Database not loaded. Call load_gold_data_tool first.")

            result = db_connection["conn"].execute(sql_query).fetchdf()
            result_json = result.to_dict(orient="records")

            logger = AuditLogger(run_id)
            logger.log("reporter", "execute_query", rows=len(result_json))

            return json.dumps({
                "query": sql_query,
                "rows": len(result_json),
                "data": result_json[:100],  # First 100 rows
            }, indent=2, default=str)

        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("reporter", "execute_query_error", error=str(e))
            raise

    @tool
    def submit_analysis_tool(analysis_json: str) -> str:
        """Submit final analysis JSON with insights and charts."""
        try:
            analysis = json.loads(analysis_json)
            scratchpad.update(analysis)
            logger = AuditLogger(run_id)
            logger.log("reporter", "submit_analysis", keys=list(analysis.keys()))
            return json.dumps({"status": "ok", "message": "Analysis submitted"}, indent=2)
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("reporter", "submit_analysis_error", error=str(e))
            raise

    return [
        inspect_gold_tables_tool,
        load_gold_data_tool,
        execute_query_tool,
        submit_analysis_tool,
    ], scratchpad, db_connection


# ─── HTML Report Generator ──────────────────────────────────────────────────

def _generate_html_report(
    analysis: dict,
    business_intent: str,
    sql_queries: list[str],
    charts_html: list[str],
    run_id: str,
) -> str:
    """Generate professional HTML report from analysis."""
    direct_answer = analysis.get("direct_answer", "Analysis complete.")
    detailed_analysis = analysis.get("detailed_analysis", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    charts_section = "".join(charts_html) if charts_html else "<p>No charts generated.</p>"
    sql_section = "<br>\n".join([f"<code>{sql}</code>" for sql in sql_queries])

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Business Report</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .header p {{
                font-size: 1.1em;
                opacity: 0.9;
            }}
            .content {{
                padding: 40px;
            }}
            .section {{
                margin-bottom: 40px;
            }}
            .section h2 {{
                color: #333;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 20px;
                font-size: 1.8em;
            }}
            .answer-box {{
                background: #f0f4ff;
                border-left: 4px solid #667eea;
                padding: 20px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .answer-box p {{
                color: #333;
                line-height: 1.6;
                font-size: 1.1em;
            }}
            .charts-container {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 30px;
            }}
            .chart-item {{
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 20px;
                background: #fafafa;
            }}
            .sql-box {{
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 15px;
                overflow-x: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }}
            .footer {{
                background: #f0f0f0;
                padding: 20px;
                text-align: center;
                color: #666;
                border-top: 1px solid #ddd;
            }}
            .meta {{
                font-size: 0.9em;
                color: #999;
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Business Analytics Report</h1>
                <p>{business_intent}</p>
            </div>
            <div class="content">
                <div class="section">
                    <h2>📊 Key Finding</h2>
                    <div class="answer-box">
                        <p>{direct_answer}</p>
                    </div>
                </div>

                <div class="section">
                    <h2>📈 Visualizations</h2>
                    <div class="charts-container">
                        {charts_section}
                    </div>
                </div>

                <div class="section">
                    <h2>🔍 Analysis</h2>
                    <p style="line-height: 1.8; color: #555;">{detailed_analysis}</p>
                </div>

                <div class="section">
                    <h2>💾 SQL Approach</h2>
                    <div class="sql-box">
                        {sql_section}
                    </div>
                </div>
            </div>
            <div class="footer">
                <p>Generated by IDAMP Data Pipeline</p>
                <div class="meta">
                    <p>Run ID: {run_id}</p>
                    <p>Generated: {timestamp}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ─── Public Entry Point ─────────────────────────────────────────────────────

def generate_report(
    gold_files: list[str],
    business_intent: str,
    run_id: str,
    task_description: str = "",
) -> str:
    """
    Generate a business report from Gold tables using AI analysis.
    Returns path to the HTML report.
    """
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace("reporter", run_id)
    trace.set_input(gold_files=gold_files, business_intent=business_intent)
    trace.set_plan("Inspect Gold tables → Load data → Execute SQL → Generate report")

    try:
        llm = _make_llm()
        tools, scratchpad, db_connection = _make_reporter_tools(gold_files, run_id)

        agent = create_react_agent(llm, tools, state_modifier=REPORTER_AGENT_PROMPT)

        input_msg = (
            f"Generate a business report answering: '{business_intent}'. "
            f"Use these Gold tables: {gold_files}. {task_description}"
        )
        result = agent.invoke({"messages": [("user", input_msg)]})

        # Extract analysis from scratchpad
        analysis = scratchpad.get("analysis", {})
        direct_answer = scratchpad.get("direct_answer", "Analysis complete.")
        detailed_analysis = scratchpad.get("detailed_analysis", "")
        charts_specs = scratchpad.get("charts", [])

        # Generate charts
        charts_html = []
        sql_queries = []
        for i, chart_spec in enumerate(charts_specs[:5]):  # Max 5 charts
            try:
                if db_connection["conn"] and "data" in chart_spec:
                    chart_html = generate_chart_from_spec(
                        pd.DataFrame(chart_spec["data"]),
                        chart_spec,
                        f"chart_{i}",
                    )
                    charts_html.append(f'<div class="chart-item">{chart_html}</div>')
            except Exception:
                pass

        # Generate HTML report
        html_report = _generate_html_report(
            analysis={
                "direct_answer": direct_answer,
                "detailed_analysis": detailed_analysis,
            },
            business_intent=business_intent,
            sql_queries=sql_queries,
            charts_html=charts_html,
            run_id=run_id,
        )

        # Save HTML report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = REPORTS_DIR / f"report_{timestamp}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)

        # Save JSON report
        json_path = REPORTS_DIR / f"report_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(scratchpad, f, indent=2, default=str)

        trace.set_output(html_report=str(html_path), json_report=str(json_path))
        trace.complete(status="success")

        logger = AuditLogger(run_id)
        logger.log(
            "reporter",
            "generate_report_complete",
            html_report=str(html_path),
            json_report=str(json_path),
        )

        return str(html_path)

    except Exception as e:
        trace.fail(str(e))
        raise
