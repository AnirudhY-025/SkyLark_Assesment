"""Streamlit chat UI for the Skylark Drones BI Agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.llm_client import LLMClient
from agent.monday_client import MondayClient, MondayAPIError


# ── Secrets / env loading ──────────────────────────────────────────────

def _get_secret(key: str, default: str = "") -> str:
    """Read from env (local) or Streamlit secrets (production)."""
    val = os.getenv(key)
    if val:
        return val
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default


# ── Page config ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Skylark Drones — BI Agent",
    page_icon="🛰️",
    layout="wide",
)

# ── Initialise clients (cached) ───────────────────────────────────────

@st.cache_resource
def _init_monday_client() -> MondayClient:
    return MondayClient(
        token=_get_secret("MONDAY_API_TOKEN"),
        work_orders_board_id=_get_secret("MONDAY_WORK_ORDERS_BOARD_ID"),
        deals_board_id=_get_secret("MONDAY_DEALS_BOARD_ID"),
    )


@st.cache_resource
def _init_llm_client() -> LLMClient:
    return LLMClient(
        api_key=_get_secret("OPENROUTER_API_KEY"),
        model=_get_secret("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    )


# ── Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🛰️ Skylark BI")
    st.caption("Business Intelligence Agent")

    monday_client = _init_monday_client()
    llm_client = _init_llm_client()

    # Connection status
    st.divider()
    st.subheader("Connection")
    if _get_secret("MONDAY_API_TOKEN"):
        try:
            connected = monday_client.test_connection()
            if connected:
                st.success("monday.com connected")
            else:
                st.error("Cannot reach monday.com — check your API token")
        except Exception:
            st.error("Connection check failed")
    else:
        st.warning("No MONDAY_API_TOKEN configured")

    wo_id = _get_secret("MONDAY_WORK_ORDERS_BOARD_ID")
    deals_id = _get_secret("MONDAY_DEALS_BOARD_ID")
    if wo_id and deals_id:
        st.info(f"Work Orders board: `{wo_id}`\n\nDeals board: `{deals_id}`")
    else:
        st.warning("Board IDs not configured")

    # Buttons
    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        monday_client.clear_cache()
        st.cache_resource.clear()
        st.toast("Cache cleared — data will be re-fetched on next query.")

    if st.button("📋 Generate Leadership Update", use_container_width=True):
        st.session_state["pending_leader_update"] = True

    # Model info
    st.divider()
    st.caption(f"Model: `{llm_client.model}`")

# ── Chat UI ────────────────────────────────────────────────────────────

st.title("🛰️ Skylark Drones — BI Agent")
st.caption("Ask me anything about your pipeline, work orders, revenue, or sector performance.")

# Init conversation history
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "Welcome! I'm your BI analyst for Skylark Drones. I can help you with:\n\n"
                "- **Pipeline health** — deal values by stage, sector breakdown\n"
                "- **Win rates** — conversion by sector, owner, or overall\n"
                "- **Work order status** — billing, collections, outstanding AR\n"
                "- **Sector performance** — revenue, pipeline, project counts\n"
                "- **Leadership updates** — structured exec-ready briefs\n\n"
                "What would you like to know?"
            ),
        }
    ]


# Display chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools_used"):
            with st.expander("📡 Data Source Trace (monday.com live query)", expanded=False):
                for tool in msg["tools_used"]:
                    st.markdown(f"**Tool Invoked:** `{tool['name']}`")
                    if tool.get("arguments"):
                        st.caption("Parameters / Filters:")
                        st.json(tool["arguments"])
                    st.caption("Raw Data Fetched from monday.com GraphQL API:")
                    st.code(tool["result_snippet"], language="json")

# Handle leadership update button
if st.session_state.get("pending_leader_update"):
    st.session_state["pending_leader_update"] = False
    user_input = "Give me a leadership update on overall performance."
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Generating leadership update from monday.com..."):
            messages_for_llm = [{"role": m["role"], "content": m.get("content", "")} for m in st.session_state["messages"]]
            response, executed_tools = llm_client.chat(messages_for_llm, monday_client)
        st.markdown(response)
        if executed_tools:
            with st.expander("📡 Data Source Trace (monday.com live query)", expanded=False):
                for tool in executed_tools:
                    st.markdown(f"**Tool Invoked:** `{tool['name']}`")
                    if tool.get("arguments"):
                        st.caption("Parameters / Filters:")
                        st.json(tool["arguments"])
                    st.caption("Raw Data Fetched from monday.com GraphQL API:")
                    st.code(tool["result_snippet"], language="json")
    st.session_state["messages"].append({
        "role": "assistant",
        "content": response,
        "tools_used": executed_tools
    })
    st.rerun()

# Chat input
if user_input := st.chat_input("Ask about pipeline, revenue, sectors, work orders..."):
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Fetching data from monday.com..."):
            # Build messages for LLM (only role + content, strip tool-related fields)
            messages_for_llm = [{"role": m["role"], "content": m.get("content", "")} for m in st.session_state["messages"]]
            response, executed_tools = llm_client.chat(messages_for_llm, monday_client)
        st.markdown(response)
        if executed_tools:
            with st.expander("📡 Data Source Trace (monday.com live query)", expanded=False):
                for tool in executed_tools:
                    st.markdown(f"**Tool Invoked:** `{tool['name']}`")
                    if tool.get("arguments"):
                        st.caption("Parameters / Filters:")
                        st.json(tool["arguments"])
                    st.caption("Raw Data Fetched from monday.com GraphQL API:")
                    st.code(tool["result_snippet"], language="json")

    st.session_state["messages"].append({
        "role": "assistant",
        "content": response,
        "tools_used": executed_tools
    })

