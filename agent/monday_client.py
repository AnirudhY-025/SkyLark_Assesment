"""Thin wrapper around monday.com GraphQL API v2."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pandas as pd
import requests


MONDAY_API_URL = "https://api.monday.com/v2"


class MondayAPIError(Exception):
    """Raised when monday.com API returns an error."""
    def __init__(self, message: str, status_code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class MondayClient:
    """Fetches board data from monday.com via GraphQL with caching."""

    def __init__(
        self,
        token: str | None = None,
        work_orders_board_id: str | None = None,
        deals_board_id: str | None = None,
        cache_ttl: int = 300,
    ):
        self.token = token or os.getenv("MONDAY_API_TOKEN", "")
        self.work_orders_board_id = work_orders_board_id or os.getenv("MONDAY_WORK_ORDERS_BOARD_ID", "")
        self.deals_board_id = deals_board_id or os.getenv("MONDAY_DEALS_BOARD_ID", "")
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "API-Version": "2024-10",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, query: str, variables: dict | None = None, retries: int = 2) -> dict:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        for attempt in range(retries + 1):
            try:
                resp = requests.post(MONDAY_API_URL, json=payload, headers=self.headers, timeout=30)
            except requests.RequestException as exc:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise MondayAPIError(f"Network error reaching monday.com: {exc}") from exc

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise MondayAPIError(
                    f"monday.com returned {resp.status_code}", status_code=resp.status_code, response_body=resp.text
                )

            if resp.status_code != 200:
                raise MondayAPIError(
                    f"monday.com HTTP {resp.status_code}", status_code=resp.status_code, response_body=resp.text
                )

            data = resp.json()
            if "errors" in data:
                raise MondayAPIError(f"GraphQL error: {data['errors']}", response_body=data)
            return data

        raise MondayAPIError("Exceeded retries")

    def _cache_key(self, board_id: str) -> str:
        return f"board_{board_id}"

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self.cache_ttl:
                return val
            del self._cache[key]
        return None

    def _set_cache(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Verify the API token is valid by fetching the account name."""
        query = """
        query { me { name email } }
        """
        try:
            self._request(query)
            return True
        except MondayAPIError:
            return False

    def get_board_schema(self, board_id: str) -> list[dict]:
        """Fetch column metadata for a board."""
        cache_key = f"schema_{board_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = """
        query ($boardId: [ID!]) {
            boards(ids: $boardId) {
                columns { id title type }
            }
        }
        """
        data = self._request(query, {"boardId": [board_id]})
        cols = data["data"]["boards"][0]["columns"] if data["data"]["boards"] else []
        self._set_cache(cache_key, cols)
        return cols

    def get_board_items(self, board_id: str) -> list[dict]:
        """Fetch all items from a board with cursor-based pagination."""
        cache_key = self._cache_key(board_id)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        all_items: list[dict] = []
        cursor: str | None = None

        while True:
            variables: dict[str, Any] = {"boardId": [board_id], "cursor": cursor}
            query = """
            query ($boardId: [ID!], $cursor: String) {
                boards(ids: $boardId) {
                    name
                    items_page(limit: 500, cursor: $cursor) {
                        cursor
                        items {
                            id
                            name
                            column_values {
                                id
                                column { title }
                                text
                                value
                            }
                        }
                    }
                }
            }
            """
            data = self._request(query, variables)
            boards = data.get("data", {}).get("boards", [])
            if not boards:
                break

            page = boards[0]["items_page"]
            all_items.extend(page["items"])
            cursor = page.get("cursor")
            if not cursor:
                break

        self._set_cache(cache_key, all_items)
        return all_items

    def boards_to_dataframe(self, items: list[dict]) -> pd.DataFrame:
        """Flatten monday.com items into a wide DataFrame keyed by column title."""
        rows = []
        for item in items:
            row: dict[str, Any] = {"item_id": item["id"], "item_name": item["name"]}
            for cv in item.get("column_values", []):
                title = cv["column"]["title"]
                # Prefer 'text' for display; fall back to parsed 'value'
                text_val = cv.get("text") or ""
                row[title] = text_val
            rows.append(row)
        return pd.DataFrame(rows)

    def get_work_orders(self) -> pd.DataFrame:
        """Fetch and flatten the Work Orders board."""
        if not self.work_orders_board_id:
            raise MondayAPIError("MONDAY_WORK_ORDERS_BOARD_ID is not configured.")
        items = self.get_board_items(self.work_orders_board_id)
        return self.boards_to_dataframe(items)

    def get_deals(self) -> pd.DataFrame:
        """Fetch and flatten the Deals board."""
        if not self.deals_board_id:
            raise MondayAPIError("MONDAY_DEALS_BOARD_ID is not configured.")
        items = self.get_board_items(self.deals_board_id)
        return self.boards_to_dataframe(items)
