from fastapi.testclient import TestClient


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_model_with_version(client: TestClient, token: str, name: str, tag: str) -> int:
    create_model = client.post(
        "/api/v1/models",
        headers=auth_header(token),
        json={
            "name": name,
            "description": "Test model",
            "owner_team": "Platform ML",
        },
    )
    assert create_model.status_code == 200, create_model.text
    model_id = create_model.json()["id"]

    create_version = client.post(
        f"/api/v1/models/{model_id}/versions",
        headers=auth_header(token),
        json={
            "version_tag": tag,
            "artifact_uri": f"s3://modelops/{name}/{tag}/model.pkl",
            "changelog": "Test version",
        },
    )
    assert create_version.status_code == 200, create_version.text
    return create_version.json()["id"]


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_viewer_cannot_create_model(client: TestClient) -> None:
    viewer_token = login(client, "viewer@modelops.local", "viewer1234")

    response = client.post(
        "/api/v1/models",
        headers=auth_header(viewer_token),
        json={
            "name": "fraud-detector",
            "description": "Viewer should not create",
            "owner_team": "Risk AI",
        },
    )

    assert response.status_code == 403


def test_admin_model_version_and_deployment_flow(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")

    create_model = client.post(
        "/api/v1/models",
        headers=auth_header(admin_token),
        json={
            "name": "fraud-detector",
            "description": "Binary classifier for fraud scoring",
            "owner_team": "Risk AI",
        },
    )
    assert create_model.status_code == 200, create_model.text
    model_id = create_model.json()["id"]

    create_version = client.post(
        f"/api/v1/models/{model_id}/versions",
        headers=auth_header(admin_token),
        json={
            "version_tag": "v1.0.0",
            "artifact_uri": "s3://modelops/fraud/v1/model.pkl",
            "changelog": "Initial production candidate",
        },
    )
    assert create_version.status_code == 200, create_version.text
    version_id = create_version.json()["id"]

    deploy = client.post(
        "/api/v1/deployments",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "environment": "production",
            "strategy": "canary",
            "status": "pending",
            "traffic_percent": 10,
            "notes": "Start at 10% traffic",
        },
    )
    assert deploy.status_code == 200, deploy.text
    deployment_id = deploy.json()["id"]

    update = client.patch(
        f"/api/v1/deployments/{deployment_id}/status",
        headers=auth_header(admin_token),
        json={"status": "running", "traffic_percent": 25},
    )
    assert update.status_code == 200, update.text
    assert update.json()["status"] == "running"
    assert update.json()["traffic_percent"] == 25


def test_inference_metrics_capture_error_rate_and_latency(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")

    create_model = client.post(
        "/api/v1/models",
        headers=auth_header(admin_token),
        json={
            "name": "churn-predictor",
            "description": "Customer churn model",
            "owner_team": "Growth ML",
        },
    )
    assert create_model.status_code == 200
    model_id = create_model.json()["id"]

    create_version = client.post(
        f"/api/v1/models/{model_id}/versions",
        headers=auth_header(admin_token),
        json={
            "version_tag": "v2.1.0",
            "artifact_uri": "s3://modelops/churn/v2/model.pkl",
            "changelog": "Improved recall",
        },
    )
    assert create_version.status_code == 200
    version_id = create_version.json()["id"]

    log_ok = client.post(
        "/api/v1/inference/logs",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "request_id": "req-100",
            "latency_ms": 120.0,
            "status_code": 200,
            "error_message": "",
        },
    )
    assert log_ok.status_code == 200, log_ok.text

    log_err = client.post(
        "/api/v1/inference/logs",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "request_id": "req-101",
            "latency_ms": 300.0,
            "status_code": 500,
            "error_message": "upstream timeout",
        },
    )
    assert log_err.status_code == 200, log_err.text

    metrics = client.get("/api/v1/inference/metrics", headers=auth_header(admin_token))
    assert metrics.status_code == 200

    payload = metrics.json()
    assert payload["total_requests"] == 2
    assert payload["error_rate"] == 0.5
    assert payload["avg_latency_ms"] == 210.0
    assert payload["p95_latency_ms"] == 120.0


def test_dashboard_summary_reports_lifecycle_and_observability_counts(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")
    version_id = create_model_with_version(client, admin_token, "recommendation-ranker", "v1.2.0")

    create_experiment = client.post(
        "/api/v1/experiments",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "run_name": "ablation-01",
            "parameters": {"lr": 0.001, "batch_size": 64},
            "metrics": {"auc": 0.92, "f1": 0.81},
            "artifact_uri": "s3://modelops/experiments/ablation-01",
            "status": "completed",
        },
    )
    assert create_experiment.status_code == 200, create_experiment.text

    create_deployment = client.post(
        "/api/v1/deployments",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "environment": "production",
            "strategy": "blue_green",
            "status": "running",
            "traffic_percent": 100,
            "notes": "Promoted to production",
        },
    )
    assert create_deployment.status_code == 200, create_deployment.text

    for request_id, latency, status_code, error_message in [
        ("req-dashboard-1", 80.0, 200, ""),
        ("req-dashboard-2", 160.0, 200, ""),
        ("req-dashboard-3", 310.0, 500, "timeout"),
    ]:
        log_response = client.post(
            "/api/v1/inference/logs",
            headers=auth_header(admin_token),
            json={
                "model_version_id": version_id,
                "request_id": request_id,
                "latency_ms": latency,
                "status_code": status_code,
                "error_message": error_message,
            },
        )
        assert log_response.status_code == 200, log_response.text

    summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert summary.status_code == 200, summary.text
    payload = summary.json()

    assert payload["total_models"] == 1
    assert payload["total_versions"] == 1
    assert payload["total_experiments"] == 1
    assert payload["active_deployments"] == 1
    assert payload["inference_metrics"]["total_requests"] == 3
    assert payload["inference_metrics"]["error_rate"] == 0.3333
    assert payload["inference_metrics"]["avg_latency_ms"] == 183.33
    assert payload["inference_metrics"]["p95_latency_ms"] == 160.0


def test_dashboard_summary_cache_is_invalidated_after_new_inference_log(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")
    version_id = create_model_with_version(client, admin_token, "fraud-ranker", "v3.0.0")

    first_log = client.post(
        "/api/v1/inference/logs",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "request_id": "req-cache-1",
            "latency_ms": 90.0,
            "status_code": 200,
            "error_message": "",
        },
    )
    assert first_log.status_code == 200, first_log.text

    initial_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert initial_summary.status_code == 200
    assert initial_summary.json()["inference_metrics"]["total_requests"] == 1

    second_log = client.post(
        "/api/v1/inference/logs",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "request_id": "req-cache-2",
            "latency_ms": 350.0,
            "status_code": 500,
            "error_message": "gateway timeout",
        },
    )
    assert second_log.status_code == 200, second_log.text

    refreshed_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert refreshed_summary.status_code == 200

    # Cache should be invalidated on writes, so second read reflects both logs.
    assert refreshed_summary.json()["inference_metrics"]["total_requests"] == 2


def test_dashboard_summary_cache_is_invalidated_after_deployment_status_change(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")
    version_id = create_model_with_version(client, admin_token, "promo-ranker", "v1.0.0")

    create_deployment = client.post(
        "/api/v1/deployments",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "environment": "production",
            "strategy": "canary",
            "status": "pending",
            "traffic_percent": 5,
            "notes": "initial canary",
        },
    )
    assert create_deployment.status_code == 200, create_deployment.text
    deployment_id = create_deployment.json()["id"]

    initial_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert initial_summary.status_code == 200
    assert initial_summary.json()["active_deployments"] == 0

    status_update = client.patch(
        f"/api/v1/deployments/{deployment_id}/status",
        headers=auth_header(admin_token),
        json={"status": "running", "traffic_percent": 20},
    )
    assert status_update.status_code == 200, status_update.text

    refreshed_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert refreshed_summary.status_code == 200
    assert refreshed_summary.json()["active_deployments"] == 1


def test_dashboard_summary_cache_is_invalidated_after_model_version_registration(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")

    initial_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert initial_summary.status_code == 200
    assert initial_summary.json()["total_models"] == 0
    assert initial_summary.json()["total_versions"] == 0

    create_model = client.post(
        "/api/v1/models",
        headers=auth_header(admin_token),
        json={
            "name": "inventory-forecaster",
            "description": "Demand forecasting",
            "owner_team": "Supply ML",
        },
    )
    assert create_model.status_code == 200, create_model.text
    model_id = create_model.json()["id"]

    create_version = client.post(
        f"/api/v1/models/{model_id}/versions",
        headers=auth_header(admin_token),
        json={
            "version_tag": "v0.1.0",
            "artifact_uri": "s3://modelops/inventory/v0.1.0/model.pkl",
            "changelog": "first version",
        },
    )
    assert create_version.status_code == 200, create_version.text

    refreshed_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert refreshed_summary.status_code == 200
    assert refreshed_summary.json()["total_models"] == 1
    assert refreshed_summary.json()["total_versions"] == 1


def test_dashboard_summary_cache_is_invalidated_after_experiment_creation(client: TestClient) -> None:
    admin_token = login(client, "admin@modelops.local", "admin1234")
    version_id = create_model_with_version(client, admin_token, "returns-predictor", "v1.0.0")

    initial_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert initial_summary.status_code == 200
    assert initial_summary.json()["total_experiments"] == 0

    create_experiment = client.post(
        "/api/v1/experiments",
        headers=auth_header(admin_token),
        json={
            "model_version_id": version_id,
            "run_name": "feature-ablation-a",
            "parameters": {"dropout": 0.2},
            "metrics": {"auc": 0.88},
            "artifact_uri": "s3://modelops/experiments/feature-ablation-a",
            "status": "completed",
        },
    )
    assert create_experiment.status_code == 200, create_experiment.text

    refreshed_summary = client.get("/api/v1/dashboard/summary", headers=auth_header(admin_token))
    assert refreshed_summary.status_code == 200
    assert refreshed_summary.json()["total_experiments"] == 1
