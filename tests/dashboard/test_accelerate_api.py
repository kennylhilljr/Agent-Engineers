import pytest
import pytest_asyncio
from dashboard.rest_api_server import app, acceleration_controller
from fastapi.testclient import TestClient


client = TestClient(app)


def test_enable_acceleration():
    response = client.post("/api/acceleration/enable?factor=2.0")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'enabled'
    assert data['acceleration_factor'] == 2.0


def test_enable_acceleration_invalid_factor():
    response = client.post("/api/acceleration/enable?factor=15.0")
    assert response.status_code == 400


def test_disable_acceleration():
    client.post("/api/acceleration/enable?factor=2.0")
    response = client.post("/api/acceleration/disable")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'disabled'


def test_get_acceleration_status():
    client.post("/api/acceleration/enable?factor=3.0")
    response = client.get("/api/acceleration/status")
    assert response.status_code == 200
    data = response.json()
    assert data['enabled'] is True
    assert data['acceleration_factor'] == 3.0


def test_submit_accelerated_task():
    client.post("/api/acceleration/enable?factor=1.5")
    response = client.post(
        "/api/acceleration/submit?task_id=test_task_1&task_data={'key':'value'}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == 'test_task_1'


def test_submit_accelerated_task_no_acceleration():
    client.post("/api/acceleration/disable")
    response = client.post(
        "/api/acceleration/submit?task_id=test_task_2&task_data={'key':'value'}"
    )
    assert response.status_code == 400


def test_get_accelerated_task_status():
    client.post("/api/acceleration/enable?factor=1.5")
    client.post("/api/acceleration/submit?task_id=task_3&task_data={'data':'test'}")
    response = client.get("/api/acceleration/task/task_3")
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == 'task_3'


def test_get_accelerated_task_not_found():
    response = client.get("/api/acceleration/task/nonexistent")
    assert response.status_code == 404


def test_get_acceleration_metrics():
    client.post("/api/acceleration/enable?factor=2.0")
    client.post("/api/acceleration/submit?task_id=metrics_task_1&task_data={}")
    response = client.get("/api/acceleration/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data['acceleration_enabled'] is True
    assert 'total_active_tasks' in data


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'


def test_multiple_enable_disable_cycles():
    for i in range(5):
        response = client.post(f"/api/acceleration/enable?factor={1.0 + i * 0.5}")
        assert response.status_code == 200
        
        response = client.post("/api/acceleration/disable")
        assert response.status_code == 200


def test_acceleration_factor_range():
    test_factors = [1.0, 1.5, 2.0, 5.0, 10.0]
    for factor in test_factors:
        response = client.post(f"/api/acceleration/enable?factor={factor}")
        assert response.status_code == 200
        assert response.json()['acceleration_factor'] == factor


def test_concurrent_task_submissions():
    client.post("/api/acceleration/enable?factor=2.0")
    for i in range(10):
        response = client.post(
            f"/api/acceleration/submit?task_id=concurrent_{i}&task_data={{}}"
        )
        assert response.status_code == 200


def test_acceleration_status_transitions():
    client.post("/api/acceleration/disable")
    response = client.get("/api/acceleration/status")
    assert response.json()['enabled'] is False
    
    client.post("/api/acceleration/enable?factor=1.5")
    response = client.get("/api/acceleration/status")
    assert response.json()['enabled'] is True
    
    client.post("/api/acceleration/disable")
    response = client.get("/api/acceleration/status")
    assert response.json()['enabled'] is False


def test_metrics_update_after_tasks():
    client.post("/api/acceleration/enable?factor=1.5")
    for i in range(5):
        client.post(f"/api/acceleration/submit?task_id=metric_task_{i}&task_data={{}}")
    
    response = client.get("/api/acceleration/metrics")
    data = response.json()
    assert data['total_active_tasks'] >= 5


def test_timestamp_in_responses():
    response = client.post("/api/acceleration/enable?factor=1.5")
    data = response.json()
    assert 'timestamp' in data
    assert data['timestamp'].endswith('Z')
