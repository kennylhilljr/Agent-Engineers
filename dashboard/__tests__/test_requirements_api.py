"""Tests for REQ-CONTROL-007: Requirement Sync to Linear.

Tests cover:
- GET /api/requirements/{ticket_key} returns 200 with requirement data
- PUT /api/requirements/{ticket_key} with sync_to_linear=false stores locally
- PUT /api/requirements/{ticket_key} with sync_to_linear=true attempts Linear sync
- Error handling when Linear API fails
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.server as server_module
from dashboard.server import DashboardServer


class TestGetRequirement(AioHTTPTestCase):
    """Tests for GET /api/requirements/{ticket_key}."""

    async def get_application(self):
        # Reset the in-memory store before each test
        server_module._requirements_store.clear()

        ds = DashboardServer(
            project_name='test-project',
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_get_requirement_returns_200_with_empty_when_not_set(self):
        """GET for unknown ticket key returns 200 with empty requirement."""
        resp = await self.client.request('GET', '/api/requirements/AI-000')
        assert resp.status == 200
        data = await resp.json()
        assert data['ticket_key'] == 'AI-000'
        assert data['requirement'] == ''

    @unittest_run_loop
    async def test_get_requirement_returns_stored_text(self):
        """GET returns the previously stored requirement text."""
        server_module._requirements_store['AI-157'] = 'When user edits requirements, changes sync to Linear.'

        resp = await self.client.request('GET', '/api/requirements/AI-157')
        assert resp.status == 200
        data = await resp.json()
        assert data['ticket_key'] == 'AI-157'
        assert data['requirement'] == 'When user edits requirements, changes sync to Linear.'

    @unittest_run_loop
    async def test_get_requirement_content_type_is_json(self):
        """Response content type is application/json."""
        resp = await self.client.request('GET', '/api/requirements/AI-001')
        assert resp.status == 200
        assert 'application/json' in resp.headers.get('Content-Type', '')


class TestPutRequirement(AioHTTPTestCase):
    """Tests for PUT /api/requirements/{ticket_key}."""

    async def get_application(self):
        server_module._requirements_store.clear()

        ds = DashboardServer(
            project_name='test-project',
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_put_requirement_stores_locally_without_linear_sync(self):
        """PUT with sync_to_linear=false stores requirement locally and returns success."""
        payload = {
            'requirement': 'The user must be able to edit requirements.',
            'sync_to_linear': False,
        }
        resp = await self.client.request(
            'PUT',
            '/api/requirements/AI-200',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['success'] is True
        assert data['ticket_key'] == 'AI-200'
        assert data['linear_synced'] is False

        # Verify stored locally
        assert server_module._requirements_store.get('AI-200') == payload['requirement']

    @unittest_run_loop
    async def test_put_requirement_updates_existing_stored_value(self):
        """PUT overwrites any existing stored requirement."""
        server_module._requirements_store['AI-300'] = 'Old requirement text.'
        payload = {
            'requirement': 'Updated requirement text.',
            'sync_to_linear': False,
        }
        resp = await self.client.request(
            'PUT',
            '/api/requirements/AI-300',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        assert server_module._requirements_store['AI-300'] == 'Updated requirement text.'

    @unittest_run_loop
    async def test_put_requirement_bad_json_returns_400(self):
        """PUT with invalid JSON body returns 400."""
        resp = await self.client.request(
            'PUT',
            '/api/requirements/AI-400',
            data='not valid json',
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data

    @unittest_run_loop
    async def test_put_requirement_missing_field_returns_400(self):
        """PUT without 'requirement' field returns 400."""
        payload = {'sync_to_linear': False}
        resp = await self.client.request(
            'PUT',
            '/api/requirements/AI-400',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
        assert 'requirement' in data['error']

    @unittest_run_loop
    async def test_put_requirement_sync_to_linear_true_calls_linear_api(self):
        """PUT with sync_to_linear=true calls update_linear_issue."""
        with patch('dashboard.server.update_linear_issue', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = True

            payload = {
                'requirement': 'Requirement synced to Linear.',
                'sync_to_linear': True,
            }
            # Ensure LINEAR_API_KEY is set so the code proceeds
            with patch.object(server_module, 'LINEAR_API_KEY', 'test-api-key'):
                resp = await self.client.request(
                    'PUT',
                    '/api/requirements/AI-157',
                    data=json.dumps(payload),
                    headers={'Content-Type': 'application/json'},
                )

            assert resp.status == 200
            data = await resp.json()
            assert data['success'] is True
            assert data['linear_synced'] is True

            mock_update.assert_called_once_with('AI-157', 'Requirement synced to Linear.')

    @unittest_run_loop
    async def test_put_requirement_sync_false_does_not_call_linear_api(self):
        """PUT with sync_to_linear=false does not call update_linear_issue."""
        with patch('dashboard.server.update_linear_issue', new_callable=AsyncMock) as mock_update:
            payload = {
                'requirement': 'No sync.',
                'sync_to_linear': False,
            }
            resp = await self.client.request(
                'PUT',
                '/api/requirements/AI-157',
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )
            assert resp.status == 200
            mock_update.assert_not_called()

    @unittest_run_loop
    async def test_put_requirement_linear_api_failure_returns_error_info(self):
        """PUT with sync_to_linear=true and Linear API failure still stores locally,
        returns success=True with linear_synced=False and linear_error."""
        with patch('dashboard.server.update_linear_issue', new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = Exception('Linear API unavailable')

            payload = {
                'requirement': 'Important requirement.',
                'sync_to_linear': True,
            }
            with patch.object(server_module, 'LINEAR_API_KEY', 'test-api-key'):
                resp = await self.client.request(
                    'PUT',
                    '/api/requirements/AI-157',
                    data=json.dumps(payload),
                    headers={'Content-Type': 'application/json'},
                )

            assert resp.status == 200
            data = await resp.json()
            # Local store must be updated despite Linear failure
            assert server_module._requirements_store.get('AI-157') == 'Important requirement.'
            assert data['success'] is True
            assert data['linear_synced'] is False
            assert 'linear_error' in data
            assert 'Linear API unavailable' in data['linear_error']

    @unittest_run_loop
    async def test_put_requirement_missing_api_key_skips_linear_sync(self):
        """PUT with sync_to_linear=true but no LINEAR_API_KEY skips sync gracefully."""
        with patch.object(server_module, 'LINEAR_API_KEY', ''):
            payload = {
                'requirement': 'Requirement without key.',
                'sync_to_linear': True,
            }
            resp = await self.client.request(
                'PUT',
                '/api/requirements/AI-157',
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data['success'] is True
            assert data['linear_synced'] is False
            assert 'linear_error' in data


class TestOptionsPreflightRequirement(AioHTTPTestCase):
    """Tests for CORS preflight on requirement endpoints."""

    async def get_application(self):
        server_module._requirements_store.clear()
        ds = DashboardServer(
            project_name='test-project',
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_options_preflight_returns_204(self):
        """OPTIONS /api/requirements/{ticket_key} returns 204 for preflight."""
        resp = await self.client.request('OPTIONS', '/api/requirements/AI-157')
        assert resp.status == 204
