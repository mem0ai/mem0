import requests
import time
import pytest
import json
import re
import threading
import queue

# Qdrant pre-check
try:
    from qdrant_client import QdrantClient
    def check_qdrant():
        try:
            client = QdrantClient(host="localhost", port=6333, timeout=10)
            client.get_collections()
            print("[QDRANT] Connection OK")
        except Exception as e:
            raise RuntimeError(f"Qdrant is not available: {e}")
    check_qdrant()
except ImportError:
    print("[QDRANT] qdrant_client not installed, skipping Qdrant pre-check.")

BASE_URL = "http://localhost:8765"
CLIENT_NAME = "cursor"
USER_ID = "rmatena"
SSE_URL = f"{BASE_URL}/mcp/{CLIENT_NAME}/sse/{USER_ID}"
MESSAGES_URL = f"{BASE_URL}/mcp/messages/"

def log_request(method, url, payload=None, headers=None):
    print(f"\n[REQUEST] {method.upper()} {url}")
    if headers is not None:
        print(f"[REQUEST HEADERS]: {json.dumps(dict(headers), indent=2, ensure_ascii=False)}")
    if payload is not None:
        print(f"[REQUEST BODY]: {json.dumps(payload, indent=2, ensure_ascii=False)}")

def log_response(label, resp):
    print(f"[{label}] RESPONSE {resp.status_code}: {resp.text}")
    print(f"[{label}] RESPONSE HEADERS: {json.dumps(dict(resp.headers), indent=2, ensure_ascii=False)}")

def sse_listener(stop_event, session_id_queue):
    with requests.get(SSE_URL, stream=True, timeout=60) as sse_resp:
        print(f"\n[SSE-LISTENER] STATUS: {sse_resp.status_code}")
        print("[SSE-LISTENER] HEADERS:", dict(sse_resp.headers))
        print("[SSE-LISTENER] STREAM DATA:")
        for line in sse_resp.iter_lines(decode_unicode=True):
            if line:
                print(f"[SSE-LISTENER] {line}")
                if line.startswith("data: "):
                    m = re.search(r"session_id=([a-f0-9]+)", line)
                    if m:
                        session_id = m.group(1)
                        # Zapiš session_id do fronty pouze jednou
                        if session_id_queue.empty():
                            session_id_queue.put(session_id)
            if stop_event.is_set():
                break

def get_session_id(session_id_queue):
    # Získej session_id z fronty, do které zapisuje listener
    try:
        session_id = session_id_queue.get(timeout=10)
    except queue.Empty:
        raise RuntimeError("Nepodařilo se získat session_id ze streamu!")
    return session_id

def test_add_and_search_memory_mcp():
    # Spusť SSE listener v samostatném vlákně a frontu pro session_id
    stop_event = threading.Event()
    session_id_queue = queue.Queue()
    sse_thread = threading.Thread(target=sse_listener, args=(stop_event, session_id_queue))
    sse_thread.start()
    try:
        session_id = get_session_id(session_id_queue)
        messages_url_with_session = f"{MESSAGES_URL}?session_id={session_id}"
        # Inicializace
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": CLIENT_NAME, "version": "1.0.0"}
            }
        }
        headers = {"Content-Type": "application/json"}
        log_request("POST", messages_url_with_session, init_payload, headers)
        resp = requests.post(messages_url_with_session, json=init_payload, headers=headers)
        log_response("INIT", resp)
        assert resp.status_code == 200
        # Přidání vzpomínky
        add_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "add_memories",
                "arguments": {"text": "Toto je testovací vzpomínka přes MCP."},
                "sessionId": session_id
            }
        }
        log_request("POST", messages_url_with_session, add_payload, headers)
        resp = requests.post(messages_url_with_session, json=add_payload, headers=headers)
        log_response("ADD", resp)
        assert resp.status_code == 200
        data = resp.json()
        print(f"[ADD] RESPONSE JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
        assert data.get("status") == "ok"
        time.sleep(3)
        # Vylistování vzpomínek
        list_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_memories",
                "arguments": {},
                "sessionId": session_id
            }
        }
        log_request("POST", messages_url_with_session, list_payload, headers)
        list_resp = requests.post(messages_url_with_session, json=list_payload, headers=headers)
        log_response("LIST", list_resp)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        print(f"[LIST] RESPONSE JSON: {json.dumps(list_data, indent=2, ensure_ascii=False)}")
        found = False
        if "result" in list_data:
            result = list_data["result"]
            if isinstance(result, list):
                for item in result:
                    if "Toto je testovací vzpomínka" in str(item):
                        found = True
                        break
            elif isinstance(result, dict) and "results" in result:
                for item in result["results"]:
                    if "Toto je testovací vzpomínka" in str(item):
                        found = True
                        break
            elif isinstance(result, str):
                if "Toto je testovací vzpomínka" in result:
                    found = True
        assert found, "Testovací vzpomínka nebyla nalezena ve výsledcích list_memories."
    finally:
        stop_event.set()
        sse_thread.join()

# Ostatní parametrizované testy by bylo vhodné upravit obdobně, pokud mají používat session_id a nové MCP API. 