def test_list_services_catalogue(client):
    res = client.get("/api/services")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 10
    voter_scheme = next((s for s in data if s["id"] == "SVC-VOTER-ID"), None)
    assert voter_scheme is not None
    assert voter_scheme["official_application_url"] == "https://voters.eci.gov.in/"
    assert voter_scheme["verification_status"] == "NEEDS_REVIEW"


def test_get_service_detail(client):
    res = client.get("/api/services/SVC-PM-KISAN")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "SVC-PM-KISAN"
    assert "https://pmkisan.gov.in/" in data["official_application_url"]
    assert data["category"] == "Agriculture & Farmers"


def test_get_service_by_code(client):
    res = client.get("/api/services/ECI-VOTER-FORM6")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "SVC-VOTER-ID"


def test_get_service_not_found(client):
    res = client.get("/api/services/SVC-NON-EXISTENT")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
