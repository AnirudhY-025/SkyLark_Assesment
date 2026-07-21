"""Tool definitions exposed to the LLM for querying monday.com data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from agent.data_cleaning import (
    flag_missing,
    is_active_stage,
    is_won_stage,
    normalize_currency,
    normalize_dates,
    normalize_deal_status,
    normalize_sector,
    normalize_text,
)
from agent.monday_client import MondayClient, MondayAPIError


def _safe_json(obj: Any) -> str:
    """Serialize to JSON, handling NaN/NaT."""
    return json.dumps(obj, default=str, ensure_ascii=False)


def _drop_junk_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove embedded header rows and empty rows from CSV imports.

    Some CSVs have mid-data rows that repeat column headers or are
    completely empty — we detect and drop them.
    """
    if df.empty:
        return df

    # Drop rows where all values are NaN/empty
    df = df.dropna(how="all")

    # Drop rows that look like embedded header repetitions
    # (e.g. a row where any of the first 6 cells matches a column name)
    col_names_lower = {str(c).strip().lower() for c in df.columns}
    def _is_junk_row(row):
        vals = [v for v in row.values[:6] if pd.notna(v) and str(v).strip()]
        matches = sum(1 for v in vals if str(v).strip().lower() in col_names_lower)
        # Junk if 2+ values match column names (more than 1 to avoid false positives)
        return matches >= 2

    mask = df.apply(_is_junk_row, axis=1)
    # Only apply if we're not dropping too many rows (>50% would be wrong)
    if mask.sum() > 0 and mask.sum() < len(df) * 0.1:
        df = df[~mask]

    return df



# ── Tool functions ─────────────────────────────────────────────────────

def get_work_orders(client: MondayClient, filters: dict | None = None) -> str:
    """Fetch work orders, apply cleaning, optional filters."""
    try:
        df = client.get_work_orders()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    df = _drop_junk_rows(df)

    if df.empty:
        return _safe_json({"error": "No work orders found on the board.", "data": [], "count": 0})

    # Normalize columns
    for col in df.columns:
        if "date" in col.lower() or col.lower().endswith("date"):
            df[col] = normalize_dates(df[col])
        elif "amount" in col.lower() or "billed" in col.lower() or "receivable" in col.lower() or "value" in col.lower() or "collected" in col.lower():
            df[col] = normalize_currency(df[col])
        elif col.lower() in ("sector", "type of work", "nature of work", "execution status", "document type", "invoice status", "collection status", "billing status", "wo status (billed)"):
            df[col] = normalize_text(df[col], title_case=False)

    if "Sector" in df.columns:
        df["Sector"] = normalize_sector(df["Sector"])

    # Apply filters
    if filters:
        if filters.get("sector") and "Sector" in df.columns:
            sector = normalize_text(pd.Series([filters["sector"]]), title_case=False).iloc[0]
            df = df[df["Sector"].str.contains(sector, case=False, na=False)]
        if filters.get("status") and "Execution Status" in df.columns:
            df = df[df["Execution Status"].str.contains(filters["status"], case=False, na=False)]
        if filters.get("client") and "Customer Name Code" in df.columns:
            df = df[df["Customer Name Code"].str.contains(filters["client"], case=False, na=False)]

    # Convert dates to string for JSON serialization
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")

    records = df.head(200).to_dict(orient="records")
    quality = flag_missing(df)

    return _safe_json({
        "data": records,
        "count": len(df),
        "truncated": len(df) > 200,
        "data_quality_notes": quality.get("notes", [])[:5],
        "columns": list(df.columns),
    })


def get_deals(client: MondayClient, filters: dict | None = None) -> str:
    """Fetch deals, apply cleaning, optional filters."""
    try:
        df = client.get_deals()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    df = _drop_junk_rows(df)

    if df.empty:
        return _safe_json({"error": "No deals found on the board.", "data": [], "count": 0})

    # Normalize
    if "Deal Status" in df.columns:
        df["Deal Status"] = normalize_deal_status(df["Deal Status"])
    if "Sector/service" in df.columns:
        df["Sector/service"] = normalize_sector(df["Sector/service"])
    if "Masked Deal value" in df.columns:
        df["Masked Deal value"] = normalize_currency(df["Masked Deal value"])
    for col in ["Close Date (A)", "Tentative Close Date", "Created Date"]:
        if col in df.columns:
            df[col] = normalize_dates(df[col])
    for col in ["Deal Name", "Owner code", "Client Code", "Deal Stage", "Product deal", "Closure Probability"]:
        if col in df.columns:
            df[col] = normalize_text(df[col], title_case=False)

    # Apply filters
    if filters:
        if filters.get("sector") and "Sector/service" in df.columns:
            df = df[df["Sector/service"].str.contains(filters["sector"], case=False, na=False)]
        if filters.get("status") and "Deal Status" in df.columns:
            df = df[df["Deal Status"].str.contains(filters["status"], case=False, na=False)]
        if filters.get("stage") and "Deal Stage" in df.columns:
            df = df[df["Deal Stage"].str.contains(filters["stage"], case=False, na=False)]
        if filters.get("owner") and "Owner code" in df.columns:
            df = df[df["Owner code"].str.contains(filters["owner"], case=False, na=False)]

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")

    records = df.head(200).to_dict(orient="records")
    quality = flag_missing(df)

    return _safe_json({
        "data": records,
        "count": len(df),
        "truncated": len(df) > 200,
        "data_quality_notes": quality.get("notes", [])[:5],
        "columns": list(df.columns),
    })


def aggregate(client: MondayClient, board: str, group_by: str, metric: str, agg: str = "sum") -> str:
    """Generic aggregation over a board.

    board: "work_orders" or "deals"
    group_by: column name to group by
    metric: numeric column to aggregate
    agg: "sum", "count", "avg", or "min"/"max"
    """
    try:
        if board == "work_orders":
            raw_df = client.get_work_orders()
        else:
            raw_df = client.get_deals()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    if raw_df.empty:
        return _safe_json({"error": f"No data found for {board}.", "data": {}})

    df = raw_df.copy()

    # Normalize sector if present
    if group_by in df.columns:
        if "sector" in group_by.lower():
            df[group_by] = normalize_sector(df[group_by])
        else:
            df[group_by] = normalize_text(df[group_by], title_case=False)

    # Normalize metric
    if metric in df.columns:
        if "amount" in metric.lower() or "billed" in metric.lower() or "value" in metric.lower() or "receivable" in metric.lower() or "collected" in metric.lower():
            df[metric] = normalize_currency(df[metric])
        else:
            # Try to convert to numeric
            df[metric] = pd.to_numeric(df[metric], errors="coerce")

    if group_by not in df.columns:
        return _safe_json({"error": f"Column '{group_by}' not found. Available: {list(df.columns)}"})
    if metric not in df.columns:
        return _safe_json({"error": f"Column '{metric}' not found. Available: {list(df.columns)}"})

    # Drop rows where metric is NaN
    df = df.dropna(subset=[metric])

    if df.empty:
        return _safe_json({"error": f"No valid numeric data found in '{metric}' for aggregation.", "data": {}})

    agg_func = {
        "sum": "sum", "count": "count", "avg": "mean",
        "mean": "mean", "min": "min", "max": "max",
    }.get(agg, "sum")

    result = getattr(df.groupby(group_by, as_index=False)[metric], agg_func)()
    result = result.sort_values(metric, ascending=False)
    result[metric] = result[metric].round(2)

    records = result.to_dict(orient="records")
    return _safe_json({
        "group_by": group_by,
        "metric": metric,
        "aggregation": agg_func,
        "data": records,
        "row_count": len(records),
    })


def get_data_quality_report(client: MondayClient, board: str) -> str:
    """Get a data quality report for a board."""
    try:
        if board == "work_orders":
            df = client.get_work_orders()
        else:
            df = client.get_deals()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    if df.empty:
        return _safe_json({"error": f"No data found for {board}."})

    quality = flag_missing(df)
    return _safe_json({
        "board": board,
        "row_count": quality["row_count"],
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "missing_summary": [n for n in quality.get("notes", []) if n],
        "last_refreshed": datetime.now().isoformat(),
    })


def cross_reference(client: MondayClient, join_key: str = "Deal Name") -> str:
    """Join work orders and deals on a shared key to find overlap.

    Default join key is 'Deal Name' (matches 'item_name' in deals with
    'Deal name masked' in work orders).
    """
    try:
        wo_df = client.get_work_orders()
        deal_df = client.get_deals()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    if wo_df.empty or deal_df.empty:
        return _safe_json({"error": "One or both boards have no data.", "work_orders_count": len(wo_df), "deals_count": len(deal_df)})

    # Prepare join keys
    wo_key_col = "Deal name masked" if "Deal name masked" in wo_df.columns else None
    deal_key_col = "Deal Name" if "Deal Name" in deal_df.columns else "item_name"

    if not wo_key_col:
        return _safe_json({"error": "Cannot find deal name column in work orders.", "wo_columns": list(wo_df.columns)})

    wo_df["_join_key"] = normalize_text(wo_df[wo_key_col], title_case=False).str.strip().str.lower()
    deal_df["_join_key"] = normalize_text(deal_df[deal_key_col], title_case=False).str.strip().str.lower()

    merged = wo_df.merge(deal_df, on="_join_key", how="inner", suffixes=("_wo", "_deal"))

    if merged.empty:
        # Try partial matching
        return _safe_json({
            "message": "No exact matches found between boards. The deal names may not correspond directly.",
            "sample_wo_names": wo_df[wo_key_col].dropna().head(10).tolist(),
            "sample_deal_names": deal_df[deal_key_col].dropna().head(10).tolist(),
            "wo_count": len(wo_df),
            "deal_count": len(deal_df),
        })

    # Summarize the join
    result_cols = [c for c in [wo_key_col, deal_key_col + "_deal", "Sector", "Sector/service", "Amount in Rupees (Excl of GST) (Masked)", "Masked Deal value", "Execution Status", "Deal Status"] if c in merged.columns]
    summary = merged[result_cols].head(100).to_dict(orient="records")

    return _safe_json({
        "join_key": join_key,
        "matched_count": len(merged),
        "work_orders_total": len(wo_df),
        "deals_total": len(deal_df),
        "data": summary,
    })


def generate_leadership_update(client: MondayClient, scope: str = "all") -> str:
    """Generate a structured leadership update brief."""
    try:
        wo_df = client.get_work_orders()
        deal_df = client.get_deals()
    except MondayAPIError as e:
        return _safe_json({"error": str(e)})

    update: dict[str, Any] = {"scope": scope, "generated_at": datetime.now().isoformat()}

    # --- Deals metrics ---
    if not deal_df.empty:
        if "Deal Status" in deal_df.columns:
            deal_df["Deal Status"] = normalize_deal_status(deal_df["Deal Status"])
        if "Masked Deal value" in deal_df.columns:
            deal_df["Masked Deal value"] = normalize_currency(deal_df["Masked Deal value"])
        if "Sector/service" in deal_df.columns:
            deal_df["Sector/service"] = normalize_sector(deal_df["Sector/service"])
        if "Deal Stage" in deal_df.columns:
            deal_df["Deal Stage"] = normalize_text(deal_df["Deal Stage"], title_case=False)

        # Filter by scope if needed
        filtered = deal_df.copy()
        if scope != "all" and "Sector/service" in filtered.columns:
            filtered = filtered[filtered["Sector/service"].str.contains(scope, case=False, na=False)]

        # Pipeline value (open deals)
        open_deals = filtered[filtered["Deal Status"].str.lower().isin(["open", "on hold"])] if "Deal Status" in filtered.columns else pd.DataFrame()
        pipeline_value = open_deals["Masked Deal value"].sum() if "Masked Deal value" in open_deals.columns and not open_deals.empty else 0

        # Pipeline by stage
        pipeline_by_stage = {}
        if not open_deals.empty and "Deal Stage" in open_deals.columns:
            stage_vals = open_deals.groupby("Deal Stage")["Masked Deal value"].sum().round(0)
            pipeline_by_stage = stage_vals.to_dict() if not stage_vals.empty else {}

        # Win rate
        won_count = len(filtered[filtered["Deal Stage"].apply(is_won_stage)]) if "Deal Stage" in filtered.columns else 0
        lost_count = len(filtered[filtered["Deal Status"].str.lower() == "lost"]) if "Deal Status" in filtered.columns else 0
        total_decided = won_count + lost_count
        win_rate = round(won_count / total_decided * 100, 1) if total_decided > 0 else 0

        # Sector breakdown
        sector_pipeline = {}
        if "Sector/service" in filtered.columns and "Masked Deal value" in filtered.columns:
            sp = filtered.groupby("Sector/service")["Masked Deal value"].sum().round(0)
            sector_pipeline = sp.to_dict() if not sp.empty else {}

        update["deals"] = {
            "total_deals": len(filtered),
            "open_deals": len(open_deals),
            "pipeline_value": round(pipeline_value, 0),
            "pipeline_by_stage": pipeline_by_stage,
            "win_rate_pct": win_rate,
            "won_count": won_count,
            "lost_count": lost_count,
            "sector_pipeline": sector_pipeline,
        }

    # --- Work Orders metrics ---
    if not wo_df.empty:
        billed_col = "Billed Value in Rupees (Excl. of GST.) (Masked)"
        collected_col = "Collected Amount in Rupees (Incl. of GST.) (Masked)"
        receivable_col = "Amount Receivable (Masked)"
        status_col = "Execution Status"

        for col in [billed_col, collected_col, receivable_col]:
            if col in wo_df.columns:
                wo_df[col] = normalize_currency(wo_df[col])

        total_billed = wo_df[billed_col].sum() if billed_col in wo_df.columns else 0
        total_collected = wo_df[collected_col].sum() if collected_col in wo_df.columns else 0
        total_receivable = wo_df[receivable_col].sum() if receivable_col in wo_df.columns else 0

        status_dist = {}
        if status_col in wo_df.columns:
            status_dist = wo_df[status_col].value_counts().to_dict()

        # Overdue / stuck
        stuck_count = len(wo_df[wo_df[status_col].str.contains("struck|stuck|pause", case=False, na=False)]) if status_col in wo_df.columns else 0

        update["work_orders"] = {
            "total_orders": len(wo_df),
            "total_billed": round(total_billed, 0),
            "total_collected": round(total_collected, 0),
            "total_receivable": round(total_receivable, 0),
            "execution_status_distribution": status_dist,
            "stuck_or_paused": stuck_count,
        }

    # --- Data quality ---
    dq_notes = []
    if not deal_df.empty:
        dq = flag_missing(deal_df)
        dq_notes.extend([f"Deals: {n}" for n in dq.get("notes", [])[:3]])
    if not wo_df.empty:
        dq = flag_missing(wo_df)
        dq_notes.extend([f"Work Orders: {n}" for n in dq.get("notes", [])[:3]])
    update["data_quality_notes"] = dq_notes[:5]

    return _safe_json(update)


# ── Tool schema for OpenAI function-calling ───────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_work_orders",
            "description": "Fetch work order data from monday.com. Returns project execution data with billing, collection, and status. Use optional filters to narrow results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filters: {sector, status, client}",
                        "properties": {
                            "sector": {"type": "string", "description": "Filter by sector (e.g. Mining, Renewables)"},
                            "status": {"type": "string", "description": "Filter by execution status (e.g. Completed, Ongoing)"},
                            "client": {"type": "string", "description": "Filter by client code"},
                        },
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deals",
            "description": "Fetch deal/pipeline data from monday.com. Returns deal stages, values, sectors, and status. Use optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filters: {sector, status, stage, owner}",
                        "properties": {
                            "sector": {"type": "string", "description": "Filter by sector"},
                            "status": {"type": "string", "description": "Filter by deal status (Open, Won, Lost)"},
                            "stage": {"type": "string", "description": "Filter by deal stage"},
                            "owner": {"type": "string", "description": "Filter by owner code"},
                        },
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate",
            "description": "Aggregate data from a board. Group by a column and compute sum/count/avg of a numeric metric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board": {"type": "string", "enum": ["work_orders", "deals"], "description": "Which board to query"},
                    "group_by": {"type": "string", "description": "Column name to group by (e.g. Sector, Deal Stage)"},
                    "metric": {"type": "string", "description": "Numeric column to aggregate (e.g. Masked Deal value, Billed Value)"},
                    "agg": {"type": "string", "enum": ["sum", "count", "avg", "mean", "min", "max"], "description": "Aggregation function"},
                },
                "required": ["board", "group_by", "metric", "agg"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_quality_report",
            "description": "Get a data quality report showing missing values and column metadata for a board.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board": {"type": "string", "enum": ["work_orders", "deals"], "description": "Which board"},
                },
                "required": ["board"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cross_reference",
            "description": "Join work orders and deals on a shared key (deal name) to find which deals have corresponding work orders and vice versa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "join_key": {"type": "string", "description": "Field to join on (default: Deal Name)", "default": "Deal Name"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_leadership_update",
            "description": "Generate a structured leadership update with headline metrics, pipeline health, win rate, revenue in execution, and data quality caveats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Scope of the update: 'all' for company-wide, or a sector name like 'Mining', 'Renewables'", "default": "all"},
                },
                "required": [],
            },
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────

def execute_tool(client: MondayClient, name: str, arguments: dict) -> str:
    """Dispatch a tool call to the right function."""
    if name == "get_work_orders":
        return get_work_orders(client, arguments.get("filters"))
    elif name == "get_deals":
        return get_deals(client, arguments.get("filters"))
    elif name == "aggregate":
        return aggregate(
            client,
            board=arguments["board"],
            group_by=arguments["group_by"],
            metric=arguments["metric"],
            agg=arguments.get("agg", "sum"),
        )
    elif name == "get_data_quality_report":
        return get_data_quality_report(client, arguments["board"])
    elif name == "cross_reference":
        return cross_reference(client, arguments.get("join_key", "Deal Name"))
    elif name == "generate_leadership_update":
        return generate_leadership_update(client, arguments.get("scope", "all"))
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})
