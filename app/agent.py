import os
import json
import sqlite3
from typing import Any

import anthropic

from .database import get_connection, get_schema

SQL_TOOL: dict = {
    "name": "run_sql",
    "description": (
        "Execute a read-only SQLite SQL query against the vulnerability database "
        "and return the results as a JSON array of row objects. "
        "Only SELECT statements are allowed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A valid SQLite SELECT statement."
            }
        },
        "required": ["query"]
    }
}


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return anthropic.Anthropic(api_key=api_key)


def _execute_sql(query: str) -> tuple[str, list[dict[str, Any]]]:
    query_stripped = query.strip().lstrip(";")
    if not query_stripped.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are permitted.")

    conn = get_connection()
    try:
        cursor = conn.execute(query_stripped)
        cols = [desc[0] for desc in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        return json.dumps(rows), rows
    except sqlite3.Error as e:
        raise ValueError(f"SQL error: {e}") from e
    finally:
        conn.close()


def run_agent(question: str) -> dict[str, Any]:
    client = _get_client()
    schema = get_schema()

    system_prompt = f"""You are PatchWatch, an expert vulnerability management analyst.
You have access to a SQLite database with the following schema:

{schema}

When a user asks a question:
1. Call the run_sql tool with a precise SQLite SELECT query to retrieve the data.
2. After seeing the results, provide a clear, concise answer in plain English.
   Reference specific numbers and hostnames from the results.
   Do not mention SQL or tool calls in your final answer.

Important query guidelines:
- Use JOINs across tables when needed (findings links assets to vulnerabilities)
- severity values: 'critical', 'high', 'medium', 'low'
- status values: 'open', 'remediated', 'accepted_risk', 'in_progress'
- environment values: 'production', 'staging', 'development'
- patch_available is 0 (false) or 1 (true)
- Dates are stored as ISO-8601 strings (YYYY-MM-DD)
"""

    messages: list[dict] = [{"role": "user", "content": question}]

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=system_prompt,
        tools=[SQL_TOOL],
        tool_choice={"type": "required"},
        messages=messages
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if not tool_use_block:
        raise RuntimeError("Claude did not produce a tool call.")

    sql_query: str = tool_use_block.input["query"]

    try:
        result_json, result_rows = _execute_sql(sql_query)
        tool_result_content = result_json
    except ValueError as e:
        result_rows = []
        tool_result_content = json.dumps({"error": str(e)})

    messages.extend([
        {"role": "assistant", "content": response.content},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_block.id,
                    "content": tool_result_content
                }
            ]
        }
    ])

    final_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=system_prompt,
        tools=[SQL_TOOL],
        messages=messages
    )

    answer_text = " ".join(
        b.text for b in final_response.content if hasattr(b, "text")
    ).strip()

    return {
        "sql": sql_query,
        "results": result_rows,
        "answer": answer_text,
        "row_count": len(result_rows)
    }