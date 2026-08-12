from fastapi.testclient import TestClient
from app.main import app


def auth_headers(client: TestClient, email: str = "admin@5grca.local", password: str = "admin123") -> dict[str, str]:
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}

def test_login_logs_and_analysis():
    with TestClient(app) as client:
        headers = auth_headers(client)
        logs=client.get("/api/logs?severity=CRITICAL",headers=headers)
        assert logs.status_code==200 and logs.json()["total"]>=3
        ticket=client.post("/api/logs/stream-ticket",headers=headers)
        assert ticket.status_code==200 and ticket.json()["expires_in"]==60
        analysis=client.post("/api/analysis/run",headers=headers,json={"question":"Apa root cause PFCP timeout?","ui_context":{"selected_nodes":["SMF-01","UPF-01"]},"retrieval_config":{"top_k":5,"alpha":.5}})
        assert analysis.status_code==200
        payload=analysis.json()
        valid={x["evidence_id"] for x in payload["evidence_bundle"]["evidence_logs"]}
        assert set(payload["rca_result"]["evidence_ids"])<=valid

        analyst_login=client.post("/api/auth/login",json={"email":"analyst@5grca.local","password":"analyst123"})
        analyst_headers={"Authorization":f"Bearer {analyst_login.json()['access_token']}"}
        assert client.post("/api/evaluation/run",headers=analyst_headers,json={"name":"Forbidden run"}).status_code==403


def test_operations_incident_and_admin_actions():
    with TestClient(app) as client:
        headers = auth_headers(client)
        logs = client.get("/api/logs?limit=3", headers=headers)
        assert logs.status_code == 200
        selected_ids = [item["log_id"] for item in logs.json()["items"][:2]]

        related = client.post(
            "/api/logs/search-related",
            headers=headers,
            json={"log_ids": selected_ids, "top_k": 5, "question": "related 5G failure events"},
        )
        assert related.status_code == 200
        assert related.json()["evidence_logs"]

        created_incident = client.post(
            "/api/incidents",
            headers=headers,
            json={
                "title": "Regression test incident",
                "description": "Created from selected live-operation logs",
                "severity": "MAJOR",
                "status": "NEW",
                "source_type": "MANUAL",
                "nodes": ["SMF-01", "UPF-01"],
            },
        )
        assert created_incident.status_code == 200
        incident = created_incident.json()
        updated_incident = client.patch(
            f"/api/incidents/{incident['id']}", headers=headers, json={"status": "INVESTIGATING"}
        )
        assert updated_incident.status_code == 200
        assert updated_incident.json()["status"] == "INVESTIGATING"

        created_user = client.post(
            "/api/users",
            headers=headers,
            json={
                "full_name": "Regression Analyst",
                "email": "regression.analyst@example.test",
                "password": "regression-password",
                "role": "ANALYST",
            },
        )
        assert created_user.status_code == 200
        user = created_user.json()
        updated_user = client.patch(f"/api/users/{user['id']}", headers=headers, json={"role": "ADMIN"})
        assert updated_user.status_code == 200
        assert updated_user.json()["role"] == "ADMIN"

        datasets = client.get("/api/datasets", headers=headers)
        assert datasets.status_code == 200 and datasets.json()
        dataset_id = datasets.json()[0]["id"]
        indexed = client.post(f"/api/datasets/{dataset_id}/index", headers=headers)
        assert indexed.status_code == 200

        evaluation = client.post(
            "/api/evaluation/run",
            headers=headers,
            json={
                "name": "Regression benchmark",
                "dataset_id": dataset_id,
                "alpha": 0.5,
                "top_k": 5,
                "time_before_minutes": 5,
                "time_after_minutes": 5,
                "embedding_model": "feature-hashing-v1",
            },
        )
        assert evaluation.status_code == 200
        assert evaluation.json()["status"] == "SUCCESS"
