def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status(client):
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


def test_health_returns_version(client):
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] == "0.1.0"


def test_health_content_type_is_json(client):
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
