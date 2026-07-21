"""End-to-end test with mock monday.com data to verify the full pipeline."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from agent.data_cleaning import (
    normalize_dates, normalize_text, normalize_currency,
    normalize_sector, normalize_deal_status, flag_missing,
    is_won_stage, is_active_stage,
)
from agent.monday_client import MondayClient


MOCK_ITEMS = [
    {
        "id": "1",
        "name": "Mining Drone Survey",
        "column_values": [
            {"id": "status", "column": {"title": "Deal Status"}, "text": "Open", "value": ""},
            {"id": "value", "column": {"title": "Masked Deal value"}, "text": "500000", "value": ""},
            {"id": "sector", "column": {"title": "Sector/service"}, "text": "Mining", "value": ""},
            {"id": "stage", "column": {"title": "Deal Stage"}, "text": "E. Proposal/Commercials Sent", "value": ""},
            {"id": "owner", "column": {"title": "Owner code"}, "text": "OWNER_003", "value": ""},
            {"id": "client", "column": {"title": "Client Code"}, "text": "COMPANY005", "value": ""},
            {"id": "created", "column": {"title": "Created Date"}, "text": "2025-06-15", "value": ""},
        ],
    },
    {
        "id": "2",
        "name": "Renewable Energy Project",
        "column_values": [
            {"id": "status", "column": {"title": "Deal Status"}, "text": "Dead", "value": ""},
            {"id": "value", "column": {"title": "Masked Deal value"}, "text": "1200000", "value": ""},
            {"id": "sector", "column": {"title": "Sector/service"}, "text": "energy", "value": ""},
            {"id": "stage", "column": {"title": "Deal Stage"}, "text": "L. Project Lost", "value": ""},
            {"id": "owner", "column": {"title": "Owner code"}, "text": "OWNER_001", "value": ""},
            {"id": "client", "column": {"title": "Client Code"}, "text": "COMPANY010", "value": ""},
            {"id": "created", "column": {"title": "Created Date"}, "text": "2025-01-10", "value": ""},
        ],
    },
    {
        "id": "3",
        "name": "Powerline Inspection Won",
        "column_values": [
            {"id": "status", "column": {"title": "Deal Status"}, "text": "Won", "value": ""},
            {"id": "value", "column": {"title": "Masked Deal value"}, "text": "300000", "value": ""},
            {"id": "sector", "column": {"title": "Sector/service"}, "text": "power line", "value": ""},
            {"id": "stage", "column": {"title": "Deal Stage"}, "text": "H. Work Order Received", "value": ""},
            {"id": "owner", "column": {"title": "Owner code"}, "text": "OWNER_002", "value": ""},
            {"id": "client", "column": {"title": "Client Code"}, "text": "COMPANY020", "value": ""},
            {"id": "created", "column": {"title": "Created Date"}, "text": "2025-09-01", "value": ""},
        ],
    },
    {
        "id": "4",
        "name": "Railways Deal",
        "column_values": [
            {"id": "status", "column": {"title": "Deal Status"}, "text": "Won", "value": ""},
            {"id": "value", "column": {"title": "Masked Deal value"}, "text": "800000", "value": ""},
            {"id": "sector", "column": {"title": "Sector/service"}, "text": "Railways", "value": ""},
            {"id": "stage", "column": {"title": "Deal Stage"}, "text": "G. Project Won", "value": ""},
            {"id": "owner", "column": {"title": "Owner code"}, "text": "OWNER_003", "value": ""},
            {"id": "client", "column": {"title": "Client Code"}, "text": "COMPANY030", "value": ""},
            {"id": "created", "column": {"title": "Created Date"}, "text": "2025-08-20", "value": ""},
        ],
    },
    {
        "id": "5",
        "name": "Mining Won Deal",
        "column_values": [
            {"id": "status", "column": {"title": "Deal Status"}, "text": "Won", "value": ""},
            {"id": "value", "column": {"title": "Masked Deal value"}, "text": "450000", "value": ""},
            {"id": "sector", "column": {"title": "Sector/service"}, "text": "Mining", "value": ""},
            {"id": "stage", "column": {"title": "Deal Stage"}, "text": "H. Work Order Received", "value": ""},
            {"id": "owner", "column": {"title": "Owner code"}, "text": "OWNER_001", "value": ""},
            {"id": "client", "column": {"title": "Client Code"}, "text": "COMPANY005", "value": ""},
            {"id": "created", "column": {"title": "Created Date"}, "text": "2025-10-01", "value": ""},
        ],
    },
]


def test_pipeline():
    mc = MondayClient.__new__(MondayClient)
    df = mc.boards_to_dataframe(MOCK_ITEMS)

    print("=== RAW DATAFRAME ===")
    print(df[["item_name", "Deal Status", "Sector/service", "Masked Deal value", "Deal Stage"]].to_string())

    # Clean
    df["Deal Status"] = normalize_deal_status(df["Deal Status"])
    df["Sector/service"] = normalize_sector(df["Sector/service"])
    df["Masked Deal value"] = normalize_currency(df["Masked Deal value"])

    print("\n=== AFTER CLEANING ===")
    print(df[["item_name", "Deal Status", "Sector/service", "Masked Deal value", "Deal Stage"]].to_string())

    # Assertions
    assert len(df) == 5, f"Expected 5 rows, got {len(df)}"
    assert df["Deal Status"].tolist() == ["Open", "Lost", "Won", "Won", "Won"], "Dead->Lost mapping failed"
    assert "Mining" in df["Sector/service"].values, "Sector normalization failed"
    assert "Renewables" in df["Sector/service"].values, "energy->Renewables mapping failed"
    assert "Powerline" in df["Sector/service"].values, "power line->Powerline mapping failed"

    # Pipeline calculation
    open_df = df[df["Deal Status"].str.lower() == "open"]
    pipeline_val = open_df["Masked Deal value"].sum()
    assert pipeline_val == 500000, f"Pipeline should be 500000, got {pipeline_val}"
    print(f"\nPipeline value (open): {pipeline_val:,.0f}")

    # Win rate
    won_count = len(df[df["Deal Stage"].apply(is_won_stage)])
    lost_count = len(df[df["Deal Status"].str.lower() == "lost"])
    total_decided = won_count + lost_count
    win_rate = won_count / total_decided * 100 if total_decided > 0 else 0
    print(f"Win rate: {win_rate:.1f}% ({won_count} won, {lost_count} lost)")
    assert win_rate == 75.0, f"Win rate should be 75%, got {win_rate}%"

    # Sector breakdown
    sector_vals = df.groupby("Sector/service")["Masked Deal value"].sum()
    print(f"\nBy sector:\n{sector_vals}")

    # Data quality
    q = flag_missing(df)
    print(f"\nQuality notes: {q['notes']}")

    print("\n=== ALL PIPELINE TESTS PASSED ===")


if __name__ == "__main__":
    test_pipeline()
