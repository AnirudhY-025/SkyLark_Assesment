"""FastAPI backend server for Skylark Drones BI Agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.llm_client import LLMClient
from agent.monday_client import MondayClient, MondayAPIError
from agent.tools import generate_leadership_update


app = FastAPI(title="Skylark Drones BI Agent API")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global instances
monday_client = MondayClient()
llm_client = LLMClient()


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = ""


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@app.get("/api/status")
def get_status():
    """Check connection to monday.com and configured boards."""
    connected = False
    try:
        connected = monday_client.test_connection()
    except Exception:
        connected = False

    return {
        "connected": connected,
        "work_orders_board_id": monday_client.work_orders_board_id,
        "deals_board_id": monday_client.deals_board_id,
        "model": llm_client.model,
    }


@app.get("/api/metrics")
def get_summary_metrics():
    """Fetch high-level KPI metrics for the header summary bar."""
    try:
        update_json = generate_leadership_update(monday_client, scope="all")
        import json
        data = json.loads(update_json)
        if "error" in data:
            return {"deals": {}, "work_orders": {}, "error": data["error"]}
        return {
            "deals": data.get("deals", {}),
            "work_orders": data.get("work_orders", {}),
            "data_quality": data.get("data_quality_notes", []),
        }
    except Exception as e:
        return {"deals": {}, "work_orders": {}, "error": str(e)}




@app.post("/api/chat")
def chat(request: ChatRequest):
    """Run agent loop on conversation history."""
    try:
        messages_dicts = [{"role": msg.role, "content": msg.content or ""} for msg in request.messages]
        response_text, executed_tools = llm_client.chat(messages_dicts, monday_client)
        return {
            "response": response_text,
            "tools_used": executed_tools,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh-cache")
def refresh_cache():
    """Clear in-memory cache for monday.com data."""
    monday_client.clear_cache()
    return {"status": "success", "message": "Cache cleared successfully"}


from fastapi.responses import FileResponse

frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"

@app.get("/")
def serve_index():
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Skylark Drones BI Agent API is live."}

if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

