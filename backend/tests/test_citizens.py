from app.models.citizen import Citizen


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


def test_create_edit_archive_restore_record(client, db):
    payload = {
        "first_name": "Test", "last_name": "Record", "date_of_birth": "2000-02-03",
        "state": "Karnataka", "district": "Bengaluru Urban", "city_or_village": "Bengaluru",
        "record_source": "synthetic",
    }
    created = client.post("/api/citizens", json=payload)
    assert created.status_code == 201
    record = created.json()
    assert record["record_source"] == "synthetic"
    assert record["is_fictional"] is True
    changed = client.patch(f"/api/citizens/{record['id']}", json={"occupation": "Teacher", "phone_number": "DEMO-PHONE-1234"})
    assert changed.status_code == 200
    archived = client.post(f"/api/citizens/{record['id']}/archive")
    assert archived.status_code == 200 and archived.json()["archived_at"]
    assert client.get(f"/api/citizens/{record['id']}").status_code == 404
    restored = client.post(f"/api/citizens/{record['id']}/restore")
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    db.query(Citizen).filter(Citizen.id == record["id"]).delete()
    db.commit()


def test_csv_import_is_transactional_and_duplicate_checked(client, db):
    csv_data = b"first_name,last_name,date_of_birth,state,district,city_or_village\nImport,Fixture,2001-01-02,Kerala,Kochi,Kochi\n"
    result = client.post("/api/citizens/import", files={"file": ("fixture.csv", csv_data, "text/csv")})
    assert result.status_code == 200
    assert result.json()["committed"] is True
    assert result.json()["imported"] == 1
    duplicate = client.post("/api/citizens/import", files={"file": ("fixture.csv", csv_data, "text/csv")})
    assert duplicate.status_code == 200
    assert duplicate.json()["committed"] is False
    assert duplicate.json()["rejected"] == 1
    db.query(Citizen).filter(Citizen.first_name == "Import", Citizen.last_name == "Fixture").delete()
    db.commit()


def test_csv_and_json_exports_are_available(client):
    csv_response = client.get("/api/citizens/export?format=csv")
    json_response = client.get("/api/citizens/export?format=json")
    assert csv_response.status_code == 200 and "text/csv" in csv_response.headers["content-type"]
    assert json_response.status_code == 200 and "citizens" in json_response.json()


def test_import_reports_missing_fields_without_committing(client):
    csv_data = b"first_name,last_name,date_of_birth,state,district,city_or_village\n,Fixture,2001-01-02,Kerala,Kochi,Kochi\n"
    response = client.post("/api/citizens/import", files={"file": ("invalid.csv", csv_data, "text/csv")})
    assert response.status_code == 200
    report = response.json()
    assert report["committed"] is False and report["imported"] == 0
    assert "first_name" in report["errors"][0]["missing_fields"]
