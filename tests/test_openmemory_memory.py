import requests

BASE_URL = "http://24gatel.eu:8765"
ADD_MEMORY_URL = f"{BASE_URL}/api/v1/memories/"


def test_add_memory():
    payload = {
        "user_id": "testuser",
        "text": "Toto je testovací vzpomínka z pytestu.",
        "metadata": {"category": "pytest"}
    }
    resp = requests.post(ADD_MEMORY_URL, json=payload)
    assert resp.status_code in (200, 201)
    data = resp.json()
    # Ověř, že odpověď obsahuje id nebo text
    assert "id" in data or "text" in data
    assert "Toto je testovací vzpomínka" in str(data) 