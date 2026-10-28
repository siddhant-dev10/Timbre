def test_get_citizens_pagination(client):
    res = client.get("/api/citizens?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 100
    assert len(data["citizens"]) == 10
    assert data["citizens"][0]["id"] == "CIT-0001"
    assert data["citizens"][0]["is_fictional"] is True
    assert data["citizens"][0]["demo_only"] is True


def test_get_citizens_search_and_filter(client):
    # Search by state
    res = client.get("/api/citizens?q=Maharashtra")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for c in data["citizens"]:
        assert "Maharashtra" in c["state"] or "Maharashtra" in c["name"]


def test_get_citizen_detail(client):
    res = client.get("/api/citizens/CIT-0001")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "CIT-0001"
    assert "DEMO-PHONE-" in data["phone_number"]
    assert "@example.com" in data["email"]
    assert data["demo_only"] is True


def test_get_citizen_not_found(client):
    res = client.get("/api/citizens/CIT-9999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_patch_citizen_dob_milestone(client):
    # Patch CIT-0001 from age 17 to age 18
    res = client.patch(
        "/api/citizens/CIT-0001",
        json={"date_of_birth": "2008-10-20"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["citizen_id"] == "CIT-0001"
    assert data["calculated_age"] == 18
    assert data["event_detected"] == "MILESTONE_AGE_18"


def test_evaluate_citizen_eligibility(client):
    res = client.post("/api/citizens/CIT-0001/evaluate")
    assert res.status_code == 200
    data = res.json()
    assert data["citizen_id"] == "CIT-0001"
    assert "eligible_services" in data
    assert len(data["eligible_services"]) > 0
    # Voter ID should be eligible now since age is 18
    voter_svcs = [s for s in data["eligible_services"] if s["id"] == "SVC-VOTER-ID"]
    assert len(voter_svcs) == 1
