from unittest.mock import patch, AsyncMock


def test_post_simulation_turning_18(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "response": "Aap 18 saal ke ho gaye hain aur Voter ID ke liye aavedan kar sakte hain.",
            "model_used": "qwen3.5:9b"
        }
        res = client.post(
            "/api/simulations",
            json={
                "citizen_id": "CIT-0001",
                "trigger_event": "MILESTONE_AGE_18"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["citizen_id"] == "CIT-0001"
        assert data["calculated_age"] == 18
        assert data["trigger_event"] == "MILESTONE_AGE_18"
        assert len(data["eligible_services"]) > 0
        sim_id = data["id"]

        # Fetch simulation by ID
        get_res = client.get(f"/api/simulations/{sim_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == sim_id


def test_list_simulations(client):
    res = client.get("/api/simulations?limit=5")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_simulation_invalid_citizen(client):
    res = client.post(
        "/api/simulations",
        json={
            "citizen_id": "CIT-9999",
            "trigger_event": "MILESTONE_AGE_18"
        }
    )
    assert res.status_code == 404
