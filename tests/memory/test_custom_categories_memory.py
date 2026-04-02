#!/usr/bin/env python3
"""
Mem0 custom_categories feature live environment test script

Tests adding memories with custom_categories and retrieving memories with filters for custom_categories.

Test cases:
  1. Add memories with custom_categories
  2. Retrieve memories and verify custom_categories exist in metadata
  3. Search memories by single categories tag via search API
  4. Search memories by multiple categories tags via search API
  5. Retrieve memories by single categories tag via API
  6. Retrieve memories by multiple categories tags via API
  7. Add memories without custom_categories (regression test)
  8. Clean up test data

Usage:
    python tests/memory/test_custom_categories_memory.py \
        --endpoint http://localhost --port 8888 \
        --token YOUR_TOKEN

    # Auto clean up data after tests
    python tests/memory/test_custom_categories_memory.py --cleanup
"""

import argparse
import json
import os
import sys
import uuid
from time import sleep
from typing import Any, Dict, List, Optional

import requests


class CustomCategoriesTester:
    """custom_categories feature test client"""

    TEST_USER_ID = f"custom-cat-user-{uuid.uuid4().hex[:8]}"

    def __init__(self, endpoint: str, port: int, token: str):
        self.base_url = f"{endpoint}:{port}"
        self.headers = {
            "X-API-Key": token,
            "Content-Type": "application/json",
        }
        self.all_memory_ids: List[str] = []
        self.memory_with_categories_ids: List[str] = []
        self.memory_without_categories_ids: List[str] = []

        print(f"\n{'=' * 70}")
        print("Mem0 custom_categories Feature Test")
        print(f"{'=' * 70}")
        print(f"Endpoint     : {self.base_url}")
        print(f"TEST_USER_ID : {self.TEST_USER_ID}")
        print(f"{'=' * 70}\n")

    # ------------------------------------------------------------------
    # Common request method
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("headers", self.headers)

        print(f"\n  -> {method} {path}")
        if "json" in kwargs:
            body_str = json.dumps(kwargs["json"], indent=4, ensure_ascii=False)
            if len(body_str) > 1500:
                body_str = body_str[:1500] + "\n    ... (truncated)"
            print(f"     Body: {body_str}")

        response = requests.request(method, url, **kwargs)

        print(f"  <- {response.status_code}")
        try:
            resp_text = json.dumps(response.json(), indent=4, ensure_ascii=False)
            if len(resp_text) > 2000:
                resp_text = resp_text[:2000] + "\n    ... (truncated)"
            print(f"     Response: {resp_text}")
        except Exception:
            print(f"     Response: {response.text[:500]}")

        return response

    def _extract_results(self, data: Any) -> List[Dict]:
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        if isinstance(data, list):
            return data
        return []

    # ------------------------------------------------------------------
    # Test 1: Add memories with custom_categories
    # ------------------------------------------------------------------
    def test_add_memory_with_custom_categories(self) -> bool:
        """Add memories with custom_categories and verify the request succeeds"""
        print("\n" + "=" * 70)
        print("Test 1: Add memories with custom_categories")
        print("=" * 70)

        body = {
            "messages": [
                {"role": "user", "content": "I love sushi and ramen. My favorite restaurant is Ichiran."}
            ],
            "user_id": self.TEST_USER_ID,
            "custom_categories": {
                "food_preferences": "User food preferences and dietary habits",
                "restaurants": "Favorite restaurants and dining experiences"
            },
            "async_mode": False,
            "infer": True,
        }

        resp = self._request("POST", "/memories", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Failed to add memory: HTTP {resp.status_code}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Response results are empty")
            return False

        for item in results:
            mid = item.get("id")
            if mid and mid != "queued":
                self.all_memory_ids.append(mid)
                self.memory_with_categories_ids.append(mid)
                print(f"  ✓ Memory created successfully: {mid}")

        if not self.memory_with_categories_ids:
            print("  ✗ No valid memory ID obtained")
            return False

        print(f"\n  ✓ Test 1 passed: Successfully added {len(self.memory_with_categories_ids)} memories with custom_categories")
        return True

    # ------------------------------------------------------------------
    # Test 3: Search memories by categories tag via search API
    # ------------------------------------------------------------------
    def test_search_with_categories_filter(self) -> bool:
        """Search memories by categories tag via search API"""
        print("\n" + "=" * 70)
        print("Test 3: Search memories by categories tag via search API")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Use search API with categories filter
        body = {
            "query": "food",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": ["food_preferences"]
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Search failed: HTTP {resp.status_code}")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Search by categories=['food_preferences'] results are empty")
            print("  ! Possible reason: LLM did not classify memory into food_preferences, or categories filter is not effective")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain food_preferences category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food_preferences" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains food_preferences category")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain food_preferences category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 3 passed: search API categories tag search succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 3 failed: some memories do not contain food_preferences category")

        return all_match

    # ------------------------------------------------------------------
    # Test 4: Search memories by multiple categories tags via search API
    # ------------------------------------------------------------------
    def test_search_with_multiple_categories_filter(self) -> bool:
        """Search memories by multiple categories tags via search API (OR logic)"""
        print("\n" + "=" * 70)
        print("Test 4: Search memories by multiple categories tags via search API")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Use search API with multiple categories filter (OR logic)
        body = {
            "query": "food",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": ["food_preferences", "restaurants"]
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Search failed: HTTP {resp.status_code}")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Search by categories=['food_preferences', 'restaurants'] results are empty")
            print("  ! Possible reason: LLM did not classify memory into specified categories, or categories filter is not effective")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories contain at least one of the specified categories
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            has_food = "food_preferences" in cats_str
            has_restaurants = "restaurants" in cats_str
            if has_food or has_restaurants:
                matched = []
                if has_food:
                    matched.append("food_preferences")
                if has_restaurants:
                    matched.append("restaurants")
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... matched categories: {matched}")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not match any specified category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 4 passed: search API multiple categories tags search succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 4 failed: some memories do not match any specified category")

        return all_match

    # ------------------------------------------------------------------
    # Test 5: Retrieve memories by single categories tag via API
    # ------------------------------------------------------------------
    def test_get_memories_by_single_category(self) -> bool:
        """Retrieve memories by single categories tag via API"""
        print("\n" + "=" * 70)
        print("Test 5: Retrieve memories by single categories tag via API")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Filter by single category (string form)
        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": "restaurants"
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories='restaurants' results are empty")
            print("  ! Possible reason: LLM did not classify memory into restaurants, or categories filter is not effective")
            # For comparison, retrieve without categories filter
            fallback_body = {
                "query": "memory",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Retrieval without categories filter returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain restaurants category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "restaurants" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains restaurants category")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain restaurants category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 5 passed: API single categories tag retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 5 failed: some memories do not contain restaurants category")

        return all_match

    # ------------------------------------------------------------------
    # Test 6: Retrieve memories by multiple categories tags via API
    # ------------------------------------------------------------------
    def test_get_memories_by_multiple_categories(self) -> bool:
        """Retrieve memories by multiple categories tags via API (OR logic)"""
        print("\n" + "=" * 70)
        print("Test 6: Retrieve memories by multiple categories tags via API")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Filter by multiple categories (list form, OR logic)
        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": ["food_preferences", "restaurants"]
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories=['food_preferences', 'restaurants'] results are empty")
            return False

        # Verify returned memories contain at least one of the specified categories
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            has_food = "food_preferences" in cats_str
            has_restaurants = "restaurants" in cats_str
            if has_food or has_restaurants:
                matched = []
                if has_food:
                    matched.append("food_preferences")
                if has_restaurants:
                    matched.append("restaurants")
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... matched categories: {matched}")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not match any specified category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 6 passed: API multiple categories tags retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 6 failed: some memories do not match any specified category")

        return all_match

    # ------------------------------------------------------------------
    # Test 7: Filter by categories partial match using contains operator
    # ------------------------------------------------------------------
    def test_search_with_categories_contains_filter(self) -> bool:
        """Search by categories partial match using contains operator via search API"""
        print("\n" + "=" * 70)
        print("Test 7: Filter by categories partial match using contains operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Use contains operator for partial matching
        # categories stored as JSON array string like '["food_preferences"]'
        # contains "food" should match memories containing "food_preferences"
        body = {
            "query": "food",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"contains": "food"}
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Search failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Search by categories={{'contains': 'food'}} results are empty")
            print("  ! Possible reason: contains filter is not effective, or LLM did not classify memory into categories containing 'food'")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories categories contain "food" substring
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food" in cats_str.lower():
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... categories contains 'food' substring (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... categories does not contain 'food' substring (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 7 passed: contains operator partial match filter succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 7 failed: some memories categories do not contain 'food' substring")

        return all_match

    # ------------------------------------------------------------------
    # Test 7b: Retrieve by categories partial match using contains operator
    # ------------------------------------------------------------------
    def test_get_memories_with_categories_contains_filter(self) -> bool:
        """Retrieve by categories partial match using contains operator via API"""
        print("\n" + "=" * 70)
        print("Test 7b: Retrieve by categories partial match using contains operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"contains": "food"}
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories={{'contains': 'food'}} results are empty")
            # For comparison, retrieve without categories filter
            fallback_body = {
                "query": "memory",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Retrieval without categories filter returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories categories contain "food" substring
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food" in cats_str.lower():
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... categories contains 'food' substring (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... categories does not contain 'food' substring (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 7b passed: contains operator partial match retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 7b failed: some memories categories do not contain 'food' substring")

        return all_match

    # ------------------------------------------------------------------
    # Test 8: Filter by categories exact match using in operator
    # ------------------------------------------------------------------
    def test_search_with_categories_in_filter(self) -> bool:
        """Search by categories exact match using in operator via search API"""
        print("\n" + "=" * 70)
        print("Test 8: Filter by categories exact match using in operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Use in operator for exact matching
        # in operator accepts a list, matching memories whose categories JSON array contains any value in the list
        body = {
            "query": "food",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"in": ["food_preferences"]}
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Search failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Search by categories={{'in': ['food_preferences']}} results are empty")
            print("  ! Possible reason: in filter is not effective, or LLM did not classify memory into food_preferences")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain food_preferences category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food_preferences" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains food_preferences category (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain food_preferences category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 8 passed: in operator exact match filter succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 8 failed: some memories do not contain food_preferences category")

        return all_match

    # ------------------------------------------------------------------
    # Test 8b: Retrieve by categories exact match using in operator
    # ------------------------------------------------------------------
    def test_get_memories_with_categories_in_filter(self) -> bool:
        """Retrieve by categories exact match using in operator via API"""
        print("\n" + "=" * 70)
        print("Test 8b: Retrieve by categories exact match using in operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"in": ["food_preferences"]}
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories={{'in': ['food_preferences']}} results are empty")
            # For comparison, retrieve without categories filter
            fallback_body = {
                "query": "memory",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Retrieval without categories filter returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain food_preferences category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food_preferences" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains food_preferences category (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain food_preferences category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 8b passed: in operator exact match retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 8b failed: some memories do not contain food_preferences category")

        return all_match

    # ------------------------------------------------------------------
    # Test 8c: Filter by multiple categories exact match using in operator (OR logic)
    # ------------------------------------------------------------------
    def test_search_with_categories_in_multiple_filter(self) -> bool:
        """Search by categories exact match using in operator with multiple values via search API (OR logic)"""
        print("\n" + "=" * 70)
        print("Test 8c: Filter by multiple categories exact match using in operator (OR logic)")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        # Use in operator with multiple values, matching memories containing any value (OR logic)
        body = {
            "query": "food",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"in": ["food_preferences", "restaurants"]}
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Search failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Search by categories={{'in': ['food_preferences', 'restaurants']}} results are empty")
            # For comparison, search without categories filter
            fallback_body = {
                "query": "food",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Search without categories filter returned {len(fallback_results)} results")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories contain at least one of the specified categories
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            has_food = "food_preferences" in cats_str
            has_restaurants = "restaurants" in cats_str
            if has_food or has_restaurants:
                matched = []
                if has_food:
                    matched.append("food_preferences")
                if has_restaurants:
                    matched.append("restaurants")
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... matched categories: {matched}")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not match any specified category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 8c passed: in operator multi-value exact match filter succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 8c failed: some memories do not match any specified category")

        return all_match

    # ------------------------------------------------------------------
    # Test 8d: Retrieve by categories partial match using icontains operator
    # ------------------------------------------------------------------
    def test_get_memories_with_categories_icontains_filter(self) -> bool:
        """Retrieve by categories case-insensitive partial match using icontains operator via API"""
        print("\n" + "=" * 70)
        print("Test 8d: Retrieve by categories partial match using icontains operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"icontains": "FOOD"}  # Test case-insensitive matching
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories={{'icontains': 'FOOD'}} results are empty")
            # For comparison, retrieve without categories filter
            fallback_body = {
                "query": "memory",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Retrieval without categories filter returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories categories contain "food" substring (case-insensitive)
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "food" in cats_str.lower():
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... categories contains 'food' substring (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... categories does not contain 'food' substring (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 8d passed: icontains operator case-insensitive partial match retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 8d failed: some memories categories do not contain 'food' substring")

        return all_match

    # ------------------------------------------------------------------
    # Test 8e: Filter by categories exclusion using nin operator
    # ------------------------------------------------------------------
    def test_get_memories_with_categories_nin_filter(self) -> bool:
        """Retrieve by categories exclusion match using nin operator via API"""
        print("\n" + "=" * 70)
        print("Test 8e: Filter by categories exclusion using nin operator")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "query": "memory",
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"nin": ["restaurants"]}  # Exclude restaurants category
            }
        }

        resp = self._request("POST", "/search", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Retrieval failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Retrieval by categories={{'nin': ['restaurants']}} results are empty")
            # For comparison, retrieve without categories filter
            fallback_body = {
                "query": "memory",
                "user_id": self.TEST_USER_ID,
            }
            fallback_resp = self._request("POST", "/search", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! Retrieval without categories filter returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify returned memories do not contain restaurants category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "restaurants" not in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... does not contain restaurants category (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... contains restaurants category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 8e passed: nin operator exclusion match retrieval succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 8e failed: some memories contain excluded category")

        return all_match

    # ------------------------------------------------------------------
    # Test 9a: GET /memories filter by categories (filters query parameter)
    # ------------------------------------------------------------------
    def test_get_memories_with_categories_filter_query_param(self) -> bool:
        """Filter memories by categories using GET /memories?filters=JSON (via curl -g)"""
        print("\n" + "=" * 70)
        print("Test 9a: GET /memories filter by categories (filters query parameter)")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        import subprocess
        import json as json_mod
        from urllib.parse import quote

        # Build filters JSON string as query parameter (compact, no spaces)
        filters_dict = {"categories": {"contains": "restaurants"}}
        filters_json = json_mod.dumps(filters_dict, separators=(',', ':'))

        url = f"{self.base_url}/memories?user_id={self.TEST_USER_ID}&filters={quote(filters_json)}"

        # Use curl -g to disable globbing (brackets in URL)
        cmd = [
            "curl", "-g", "-s", "-w", "\n%{http_code}",
            "-X", "GET",
            "-H", f"X-API-Key: {self.headers.get('X-API-Key', '')}",
            "-H", "Content-Type: application/json",
            url,
        ]
        print(f"\n  -> curl -g GET {url}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout.strip()
        except Exception as e:
            print(f"  ✗ curl command failed: {e}")
            return False

        # Parse response: last line is HTTP status code
        lines = output.rsplit("\n", 1)
        if len(lines) == 2:
            body_str, status_code_str = lines
        else:
            body_str = output
            status_code_str = "0"

        try:
            status_code = int(status_code_str)
        except ValueError:
            status_code = 0

        print(f"  <- {status_code}")
        if len(body_str) > 2000:
            print(f"     Response: {body_str[:2000]}\n    ... (truncated)")
        else:
            print(f"     Response: {body_str}")

        if status_code != 200:
            print(f"  ✗ GET /memories with filters failed: HTTP {status_code}")
            # For comparison, retrieve without filters
            fallback_resp = self._request("GET", f"/memories?user_id={self.TEST_USER_ID}")
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! GET /memories without filters returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        try:
            data = json_mod.loads(body_str)
        except json_mod.JSONDecodeError as e:
            print(f"  ✗ Failed to parse response JSON: {e}")
            return False

        results = self._extract_results(data)

        if not results:
            print("  ✗ GET /memories filter by categories contains 'restaurants' results are empty")
            # For comparison, retrieve without filters
            fallback_resp = self._request("GET", f"/memories?user_id={self.TEST_USER_ID}")
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! GET /memories without filters returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain restaurants category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "restaurants" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains restaurants category (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain restaurants category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 9a passed: GET /memories filter by categories succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 9a failed: some memories do not contain restaurants category")

        return all_match

    # ------------------------------------------------------------------
    # Test 9b: POST /memories/list filter by categories
    # ------------------------------------------------------------------
    def test_post_memories_list_with_categories_filter(self) -> bool:
        """Filter memories by categories using POST /memories/list"""
        print("\n" + "=" * 70)
        print("Test 9b: POST /memories/list filter by categories")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"contains": "restaurants"}
            }
        }

        resp = self._request("POST", "/memories/list", json=body)
        if resp.status_code != 200:
            print(f"  ✗ POST /memories/list failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ POST /memories/list filter by categories contains 'restaurants' results are empty")
            # For comparison, retrieve without filters
            fallback_body = {"user_id": self.TEST_USER_ID}
            fallback_resp = self._request("POST", "/memories/list", json=fallback_body)
            if fallback_resp.status_code == 200:
                fallback_results = self._extract_results(fallback_resp.json())
                print(f"  ! POST /memories/list without filters returned {len(fallback_results)} memories")
                for mem in fallback_results:
                    meta = mem.get("metadata", {}) or {}
                    cats = meta.get("categories")
                    print(f"     Memory {mem.get('id', '')[:12]}... categories={cats}")
            return False

        # Verify all returned memories contain restaurants category
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            if "restaurants" in cats_str:
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... contains restaurants category (categories={cats_str})")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not contain restaurants category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 9b passed: POST /memories/list filter by categories succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 9b failed: some memories do not contain restaurants category")

        return all_match

    # ------------------------------------------------------------------
    # Test 9c: POST /memories/list filter by multiple categories
    # ------------------------------------------------------------------
    def test_post_memories_list_with_multiple_categories_filter(self) -> bool:
        """Filter memories by multiple categories using POST /memories/list"""
        print("\n" + "=" * 70)
        print("Test 9c: POST /memories/list filter by multiple categories")
        print("=" * 70)

        if not self.memory_with_categories_ids:
            print("  ✗ Precondition not met: no memory IDs with custom_categories")
            return False

        body = {
            "user_id": self.TEST_USER_ID,
            "filters": {
                "categories": {"in": ["food_preferences", "restaurants"]}
            }
        }

        resp = self._request("POST", "/memories/list", json=body)
        if resp.status_code != 200:
            print(f"  ✗ POST /memories/list failed: HTTP {resp.status_code}")
            try:
                print(f"     Response: {resp.text[:500]}")
            except Exception:
                pass
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ POST /memories/list filter by multiple categories results are empty")
            return False

        # Verify returned memories contain at least one of the specified categories
        all_match = True
        for mem in results:
            meta = mem.get("metadata", {}) or {}
            cats_str = meta.get("categories", "")
            has_food = "food_preferences" in cats_str
            has_restaurants = "restaurants" in cats_str
            if has_food or has_restaurants:
                matched = []
                if has_food:
                    matched.append("food_preferences")
                if has_restaurants:
                    matched.append("restaurants")
                print(f"  ✓ Memory {mem.get('id', '')[:12]}... matched categories: {matched}")
            else:
                print(f"  ✗ Memory {mem.get('id', '')[:12]}... does not match any specified category (categories={cats_str})")
                all_match = False

        if all_match:
            print(f"\n  ✓ Test 9c passed: POST /memories/list filter by multiple categories succeeded, returned {len(results)} memories")
        else:
            print(f"\n  ✗ Test 9c failed: some memories do not match any specified category")

        return all_match

    # ------------------------------------------------------------------
    # Test 10: Add memories without custom_categories (regression test)
    # ------------------------------------------------------------------
    def test_add_memory_without_custom_categories(self) -> bool:
        """Add memories without custom_categories and verify behavior is unchanged"""
        print("\n" + "=" * 70)
        print("Test 10: Add memories without custom_categories (regression test)")
        print("=" * 70)

        body = {
            "messages": [
                {"role": "user", "content": "I enjoy hiking in the mountains on weekends."}
            ],
            "user_id": self.TEST_USER_ID,
            "async_mode": False,
            "infer": False,
        }

        resp = self._request("POST", "/memories", json=body)
        if resp.status_code != 200:
            print(f"  ✗ Failed to add memory: HTTP {resp.status_code}")
            return False

        data = resp.json()
        results = self._extract_results(data)

        if not results:
            print("  ✗ Response results are empty")
            return False

        for item in results:
            mid = item.get("id")
            if mid and mid != "queued":
                self.all_memory_ids.append(mid)
                self.memory_without_categories_ids.append(mid)
                print(f"  ✓ Memory created successfully: {mid}")

        if not self.memory_without_categories_ids:
            print("  ✗ No valid memory ID obtained")
            return False

        # Verify the memory metadata does not contain custom_categories
        sleep(1)
        memory_id = self.memory_without_categories_ids[0]
        resp2 = self._request("GET", f"/memories/{memory_id}")
        if resp2.status_code == 200:
            data2 = resp2.json()
            results2 = self._extract_results(data2)
            memory = results2[0] if results2 else data2
            metadata = memory.get("metadata", {}) or {}
            cc = metadata.get("custom_categories")
            if cc is None:
                print(f"  ✓ Memory without custom_categories correctly has no custom_categories in metadata")
            else:
                print(f"  ✗ Memory without custom_categories unexpectedly contains custom_categories in metadata: {cc}")
                return False

        print(f"\n  ✓ Test 10 passed: memories without custom_categories behave normally")
        return True

    # ------------------------------------------------------------------
    # Cleanup: Delete test memories
    # ------------------------------------------------------------------
    def cleanup(self) -> bool:
        """Delete all memories created during tests"""
        print("\n" + "=" * 70)
        print("Cleanup: Delete test memories")
        print("=" * 70)

        if not self.all_memory_ids:
            print("  No memories to clean up")
            return True

        success_count = 0
        fail_count = 0

        for mid in self.all_memory_ids:
            resp = self._request("DELETE", f"/memories/{mid}")
            if resp.status_code == 200:
                success_count += 1
                print(f"  ✓ Deleted successfully: {mid}")
            else:
                fail_count += 1
                print(f"  ✗ Delete failed: {mid} (HTTP {resp.status_code})")

        # Also try batch delete by user_id
        resp = self._request("DELETE", f"/memories", json={
            "user_id": self.TEST_USER_ID
        })
        if resp.status_code == 200:
            print(f"  ✓ Batch delete user_id={self.TEST_USER_ID} memories succeeded")

        print(f"\n  Cleanup complete: succeeded {success_count}, failed {fail_count}")
        return fail_count == 0

    # ------------------------------------------------------------------
    # Run all tests
    # ------------------------------------------------------------------
    def run_all_tests(self) -> bool:
        """Run all tests in order"""
        tests = [
            ("Add memories with custom_categories", self.test_add_memory_with_custom_categories),
            ("Search by single categories tag via search API", self.test_search_with_categories_filter),
            ("Search by multiple categories tags via search API", self.test_search_with_multiple_categories_filter),
            ("Retrieve by single categories tag via API", self.test_get_memories_by_single_category),
            ("Retrieve by multiple categories tags via API", self.test_get_memories_by_multiple_categories),
            ("Filter by categories partial match using contains (search)", self.test_search_with_categories_contains_filter),
            ("Filter by categories partial match using contains (retrieve)", self.test_get_memories_with_categories_contains_filter),
            ("Filter by categories exact match using in (search)", self.test_search_with_categories_in_filter),
            ("Filter by categories exact match using in (retrieve)", self.test_get_memories_with_categories_in_filter),
            ("Filter by multiple categories exact match using in (OR logic)", self.test_search_with_categories_in_multiple_filter),
            ("Filter by categories case-insensitive partial match using icontains", self.test_get_memories_with_categories_icontains_filter),
            ("Filter by categories exclusion using nin", self.test_get_memories_with_categories_nin_filter),
            ("GET /memories filter by categories (filters query parameter)", self.test_get_memories_with_categories_filter_query_param),
            ("POST /memories/list filter by categories", self.test_post_memories_list_with_categories_filter),
            ("POST /memories/list filter by multiple categories", self.test_post_memories_list_with_multiple_categories_filter),
            ("Add memories without custom_categories (regression test)", self.test_add_memory_without_custom_categories),
            ("Clean up test data", self.cleanup),
        ]

        results = []
        for i, (name, test_func) in enumerate(tests, 1):
            print(f"\n{'#' * 70}")
            print(f"# Test {i}/{len(tests)}: {name}")
            print(f"{'#' * 70}")

            try:
                passed = test_func()
            except Exception as e:
                print(f"  ✗ Test exception: {e}")
                import traceback
                traceback.print_exc()
                passed = False

            results.append((name, passed))
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"\n  Result: {status}")

            # Wait between tests
            if i < len(tests):
                sleep(2)

        # Summary
        print(f"\n\n{'=' * 70}")
        print("Test Summary")
        print(f"{'=' * 70}")
        passed_count = 0
        for name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}  {name}")
            if passed:
                passed_count += 1

        total = len(results)
        print(f"\n  Total: {passed_count}/{total} passed")
        print(f"{'=' * 70}\n")

        return passed_count == total


def main():
    parser = argparse.ArgumentParser(description="Mem0 custom_categories feature test")
    parser.add_argument("--endpoint", default=os.getenv("MEM0_ENDPOINT", "http://localhost"),
                        help="API endpoint (default: http://localhost)")
    parser.add_argument("--port", type=int, default=int(os.getenv("MEM0_PORT", "8888")),
                        help="API port (default: 8888)")
    parser.add_argument("--token", default=os.getenv("MEM0_API_KEY", ""),
                        help="API token")
    parser.add_argument("--cleanup", action="store_true",
                        help="Only run cleanup")

    args = parser.parse_args()

    if not args.token:
        print("Error: --token is required or set MEM0_API_KEY environment variable")
        sys.exit(1)

    tester = CustomCategoriesTester(
        endpoint=args.endpoint,
        port=args.port,
        token=args.token,
    )

    if args.cleanup:
        tester.cleanup()
    else:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
