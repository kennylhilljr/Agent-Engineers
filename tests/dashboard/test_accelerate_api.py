"""
Integration tests for Acceleration API endpoints (AI-263).

Tests cover:
- POST /api/acceleration/enable
- POST /api/acceleration/disable
- GET /api/acceleration/status
- Error handling and validation
"""

import pytest
from aiohttp import web
from dashboard.rest_api_server import RESTAPIServer
from pathlib import Path
import json


@pytest.fixture
async def server():
    """Create a test REST API server instance."""
    test_server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=Path("/tmp/test-metrics"),
        port=8420,
        host="127.0.0.1"
    )
    yield test_server
    # Cleanup would go here if needed


@pytest.fixture
async def client(aiohttp_client, server):
    """Create a test client for the REST API server."""
    return await aiohttp_client(server.app)


class TestAccelerationAPI:
    """Test suite for acceleration API endpoints."""

    @pytest.mark.asyncio
    async def test_enable_acceleration_success(self, client):
        """Test enabling acceleration with valid parameters."""
        response = await client.post(
            '/api/acceleration/enable',
            json={'factor': 2.5, 'mode': 'enabled'}
        )

        assert response.status == 200
        data = await response.json()

        assert data['status'] == 'enabled'
        assert data['factor'] == 2.5
        assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_enable_acceleration_missing_factor(self, client):
        """Test enabling acceleration without factor parameter."""
        response = await client.post(
            '/api/acceleration/enable',
            json={}
        )

        assert response.status == 400
        data = await response.json()
        assert 'error' in data
        assert 'factor' in data['error'].lower()

    @pytest.mark.asyncio
    async def test_enable_acceleration_invalid_factor_too_high(self, client):
        """Test enabling acceleration with factor > 10.0."""
        response = await client.post(
            '/api/acceleration/enable',
            json={'factor': 15.0}
        )

        assert response.status == 400
        data = await response.json()
        assert 'error' in data
        assert '1.0 and 10.0' in data['error']

    @pytest.mark.asyncio
    async def test_enable_acceleration_invalid_factor_too_low(self, client):
        """Test enabling acceleration with factor < 1.0."""
        response = await client.post(
            '/api/acceleration/enable',
            json={'factor': 0.5}
        )

        assert response.status == 400
        data = await response.json()
        assert 'error' in data
        assert '1.0 and 10.0' in data['error']

    @pytest.mark.asyncio
    async def test_enable_acceleration_invalid_json(self, client):
        """Test enabling acceleration with invalid JSON body."""
        response = await client.post(
            '/api/acceleration/enable',
            data='not valid json',
            headers={'Content-Type': 'application/json'}
        )

        assert response.status == 400
        data = await response.json()
        assert 'error' in data

    @pytest.mark.asyncio
    async def test_enable_acceleration_batch_mode(self, client):
        """Test enabling acceleration in batch mode."""
        response = await client.post(
            '/api/acceleration/enable',
            json={'factor': 3.0, 'mode': 'batch'}
        )

        assert response.status == 200
        data = await response.json()

        assert data['status'] == 'enabled'
        assert data['factor'] == 3.0
        assert data['mode'] == 'batch'

    @pytest.mark.asyncio
    async def test_disable_acceleration(self, client):
        """Test disabling acceleration."""
        # First enable it
        await client.post(
            '/api/acceleration/enable',
            json={'factor': 2.0}
        )

        # Now disable
        response = await client.post('/api/acceleration/disable')

        assert response.status == 200
        data = await response.json()

        assert data['status'] == 'disabled'
        assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_get_acceleration_status(self, client):
        """Test getting acceleration status."""
        response = await client.get('/api/acceleration/status')

        assert response.status == 200
        data = await response.json()

        assert 'enabled' in data
        assert 'mode' in data
        assert 'acceleration_factor' in data
        assert 'max_concurrent_tasks' in data
        assert 'metrics' in data
        assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_acceleration_status_after_enable(self, client):
        """Test status reflects enabled state."""
        # Enable acceleration
        await client.post(
            '/api/acceleration/enable',
            json={'factor': 4.0}
        )

        # Check status
        response = await client.get('/api/acceleration/status')
        data = await response.json()

        assert data['enabled'] is True
        assert data['acceleration_factor'] == 4.0

    @pytest.mark.asyncio
    async def test_acceleration_status_after_disable(self, client):
        """Test status reflects disabled state."""
        # Enable then disable
        await client.post(
            '/api/acceleration/enable',
            json={'factor': 3.0}
        )
        await client.post('/api/acceleration/disable')

        # Check status
        response = await client.get('/api/acceleration/status')
        data = await response.json()

        assert data['enabled'] is False
        assert data['acceleration_factor'] == 1.0
        assert data['mode'] == 'disabled'

    @pytest.mark.asyncio
    async def test_enable_acceleration_idempotent(self, client):
        """Test that enabling acceleration multiple times works correctly."""
        # Enable first time
        response1 = await client.post(
            '/api/acceleration/enable',
            json={'factor': 2.0}
        )
        assert response1.status == 200

        # Enable second time with different factor
        response2 = await client.post(
            '/api/acceleration/enable',
            json={'factor': 5.0}
        )
        assert response2.status == 200
        data = await response2.json()
        assert data['factor'] == 5.0

    @pytest.mark.asyncio
    async def test_acceleration_metrics_in_status(self, client):
        """Test that metrics are included in status response."""
        response = await client.get('/api/acceleration/status')
        data = await response.json()

        metrics = data['metrics']
        assert 'active_tasks' in metrics
        assert 'completed_tasks' in metrics
        assert 'failed_tasks' in metrics
        assert 'queue_size' in metrics
        assert 'avg_task_duration' in metrics
        assert 'total_tasks_processed' in metrics

    @pytest.mark.asyncio
    async def test_enable_acceleration_factor_boundaries(self, client):
        """Test enabling acceleration at boundary values."""
        # Test minimum valid factor
        response_min = await client.post(
            '/api/acceleration/enable',
            json={'factor': 1.0}
        )
        assert response_min.status == 200

        # Test maximum valid factor
        response_max = await client.post(
            '/api/acceleration/enable',
            json={'factor': 10.0}
        )
        assert response_max.status == 200
        data = await response_max.json()
        assert data['factor'] == 10.0
