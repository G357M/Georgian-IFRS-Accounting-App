from fastapi.testclient import TestClient
from new_system.api.main import app

client = TestClient(app)

def test_login_for_access_token():
    response = client.post("/api/v1/auth/token", data={"username": "testuser", "password": "testpass"})
    assert response.status_code == 200
    json_response = response.json()
    assert "access_token" in json_response
    assert "refresh_token" in json_response
    assert json_response["token_type"] == "bearer"

def test_login_fails_with_wrong_password():
    response = client.post("/api/v1/auth/token", data={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
