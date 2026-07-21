"""Helper script to discover monday.com board IDs and test connection.

Run this locally: python discover_boards.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from agent.monday_client import MondayClient, MondayAPIError


def main():
    token = os.getenv("MONDAY_API_TOKEN", "")
    if not token:
        print("ERROR: Set MONDAY_API_TOKEN in .env first")
        return

    client = MondayClient(token=token)

    print("Testing connection...")
    if not client.test_connection():
        print("FAILED: Cannot connect to monday.com. Check your API token.")
        return
    print("OK: Connected to monday.com\n")

    # Fetch all boards
    query = """
    query { boards { id name workspace_id } }
    """
    try:
        data = client._request(query)
        boards = data["data"]["boards"]
    except MondayAPIError as e:
        print(f"ERROR fetching boards: {e}")
        return

    print(f"Found {len(boards)} boards:\n")
    print(f"{'Board Name':<40} {'Board ID':<15}")
    print("-" * 55)
    for b in boards:
        print(f"{b['name']:<40} {b['id']:<15}")

    print("\n" + "=" * 55)
    print("Copy the board IDs into your .env file:")
    print("  MONDAY_WORK_ORDERS_BOARD_ID=<id>")
    print("  MONDAY_DEALS_BOARD_ID=<id>")

    # Try to fetch a sample from each board
    for b in boards:
        print(f"\n--- Sampling board: {b['name']} (ID: {b['id']}) ---")
        try:
            items = client.get_board_items(b["id"])
            df = client.boards_to_dataframe(items[:5])
            print(f"  Columns: {list(df.columns)}")
            print(f"  Sample rows: {len(df)}")
            print(df.head(3).to_string(max_colwidth=30))
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()
