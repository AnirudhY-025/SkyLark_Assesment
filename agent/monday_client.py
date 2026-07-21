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
        self.token = token
        self.work_orders_board_id = work_orders_board_id
        self.deals_board_id = deals_board_id
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    def get_token(self) -> str:
        return self.token or os.getenv("MONDAY_API_TOKEN", "")

    def get_work_orders_board_id(self) -> str:
        return self.work_orders_board_id or os.getenv("MONDAY_WORK_ORDERS_BOARD_ID", "")

    def get_deals_board_id(self) -> str:
        return self.deals_board_id or os.getenv("MONDAY_DEALS_BOARD_ID", "")

    def _request(self, query: str, variables: dict | None = None, retries: int = 2) -> dict:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {
            "Authorization": self.get_token(),
            "Content-Type": "application/json",
            "API-Version": "2024-10",
        }

        for attempt in range(retries + 1):
            try:
                resp = requests.post(MONDAY_API_URL, json=payload, headers=headers, timeout=30)
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
        query ($board_id: [ID!]!) {
          boards(ids: $board_id) {
            columns {
              id
              title
              type
            }
          }
        }
        """
        data = self._request(query, {"board_id": [board_id]})
        columns = data.get("data", {}).get("boards", [{}])[0].get("columns", [])
        self._set_cache(cache_key, columns)
        return columns

    def get_board_items(self, board_id: str) -> pd.DataFrame:
        """Fetch all items from a board with pagination."""
        cache_key = self._cache_key(board_id)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        all_items: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            if cursor:
                query = """
                query ($cursor: String!) {
                  next_items_page(cursor: $cursor, limit: 100) {
                    cursor
                    items {
                      id
                      name
                      column_values {
                        id
                        text
                        value
                      }
                    }
                  }
                }
                """
                res = self._request(query, {"cursor": cursor})
                page_data = res.get("data", {}).get("next_items_page", {})
            else:
                query = """
                query ($board_id: [ID!]!) {
                  boards(ids: $board_id) {
                    items_page(limit: 100) {
                      cursor
                      items {
                        id
                        name
                        column_values {
                          id
                          text
                          value
                        }
                      }
                    }
                  }
                }
                """
                res = self._request(query, {"board_id": [board_id]})
                boards = res.get("data", {}).get("boards", [])
                if not boards:
                    break
                page_data = boards[0].get("items_page", {})

            items = page_data.get("items", [])
            cursor = page_data.get("cursor")

            for item in items:
                row: dict[str, Any] = {
                  "item_id": item.get("id"),
                  "item_name": item.get("name"),
                }
                for cv in item.get("column_values", []):
                    col_id = cv.get("id")
                    text_val = cv.get("text")
                    row[col_id] = text_val
                all_items.append(row)

            if not cursor or not items:
                break

        df = pd.DataFrame(all_items)
        if not df.empty:
            schema = self.get_board_schema(board_id)
            rename_map = {col["id"]: col["title"] for col in schema}
            df = df.rename(columns=rename_map)

        self._set_cache(cache_key, df)
        return df

    def get_work_orders(self) -> pd.DataFrame:
        """Fetch and return Work Orders dataframe."""
        board_id = self.get_work_orders_board_id()
        if not board_id:
            raise MondayAPIError("MONDAY_WORK_ORDERS_BOARD_ID is not configured.")
        return self.get_board_items(board_id)

    def get_deals(self) -> pd.DataFrame:
        """Fetch and return Deals dataframe."""
        board_id = self.get_deals_board_id()
        if not board_id:
            raise MondayAPIError("MONDAY_DEALS_BOARD_ID is not configured.")
        return self.get_board_items(board_id)
