import requests
import time
import pytest

BASE_URL = "http://24gatel.eu:8765"
MCP_URL = f"{BASE_URL}/mcp/messages/?session_id=pytest-session"


def test_add_and_search_memory_mcp():
    # Přidání vzpomínky
    payload = {
        "type": "AddMemoryRequest",
        "user_id": "rmatena",
        "text": "Toto je testovací vzpomínka přes MCP.",
        "metadata": {"category": "pytest"}
    }
    resp = requests.post(MCP_URL, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"

    # Počkej na indexaci
    time.sleep(2)

    # Vyhledání vzpomínek s obecnějším dotazem
    search_payload = {
        "type": "SearchMemoriesRequest",
        "user_id": "rmatena",
        "query": "testovací"
    }
    search_resp = requests.post(MCP_URL, json=search_payload)
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    print("SEARCH RESPONSE:", search_data)
    # Ověř, že mezi výsledky je naše testovací vzpomínka
    found = False
    for item in search_data.get("results", []):
        if "Toto je testovací vzpomínka" in str(item):
            found = True
            break
    assert found, "Testovací vzpomínka nebyla nalezena ve výsledcích vyhledávání." 

@pytest.mark.parametrize("search_payload", [
    # Původní varianta
    {"type": "SearchMemoriesRequest", "user_id": "rmatena", "query": "testovací"},
    # Prázdný query
    {"type": "SearchMemoriesRequest", "user_id": "rmatena", "query": ""},
    # Dotaz pouze s user_id
    {"type": "SearchMemoriesRequest", "user_id": "rmatena"},
    # Dotaz s user_id a metadata
    {"type": "SearchMemoriesRequest", "user_id": "rmatena", "metadata": {"category": "pytest"}},
    # Dotaz s user_id a limit
    {"type": "SearchMemoriesRequest", "user_id": "rmatena", "query": "testovací", "limit": 10},
    # Dotaz s user_id, query a session_id
    {"type": "SearchMemoriesRequest", "user_id": "rmatena", "query": "testovací", "session_id": "pytest-session"},
])
def test_search_memory_mcp(search_payload):
    # Přidání vzpomínky (jen při prvním testu)
    if search_payload == {"type": "SearchMemoriesRequest", "user_id": "rmatena", "query": "testovací"}:
        payload = {
            "type": "AddMemoryRequest",
            "user_id": "rmatena",
            "text": "Toto je testovací vzpomínka přes MCP.",
            "metadata": {"category": "pytest"}
        }
        resp = requests.post(MCP_URL, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        time.sleep(2)
    # Test vyhledávání
    search_resp = requests.post(MCP_URL, json=search_payload)
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    print(f"SEARCH PAYLOAD: {search_payload}\nSEARCH RESPONSE: {search_data}\n")
    # Ověř, že odpověď je slovník a obsahuje status
    assert isinstance(search_data, dict)
    assert "status" in search_data 