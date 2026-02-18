"""Tests for AI-90 + AI-91: Requirement View and Edit (REQ-CONTROL-008/009).

Tests cover:
- GET /api/requirements/{ticket_key} returns full requirement with all fields
- PUT /api/requirements/{ticket_key} saves edited description
- GET after PUT returns updated description
- sync_to_linear toggle persists across requests
- Unknown ticket returns 404
- POST /api/requirements/{ticket_key}/sync marks requirement as synced
- POST sync on unknown ticket returns 404
- Legacy compatibility: plain text in requirements cache still returned
- PUT with edited_description field (new format)
- PUT with requirements field (legacy format)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import RESTAPIServer


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_server(tmp_path: Path) -> RESTAPIServer:
    """Create a RESTAPIServer with a temp metrics dir."""
    return RESTAPIServer(
        project_name="test-requirements",
        metrics_dir=tmp_path,
        port=18420,
        host="127.0.0.1",
    )


def _reset_state():
    """Reset all requirements-related state between tests."""
    rest_module._requirements_store.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()


@pytest.fixture
def tmp_path_fixture(tmp_path):
    return tmp_path


@pytest.fixture
async def client(tmp_path):
    """Create an aiohttp test client around a fresh RESTAPIServer."""
    _reset_state()
    server = _make_server(tmp_path)
    async with TestClient(TestServer(server.app)) as c:
        yield c
    _reset_state()


# ---------------------------------------------------------------------------
# GET /api/requirements/{ticket_key}
# ---------------------------------------------------------------------------

class TestGetRequirement:
    """Tests for GET /api/requirements/{ticket_key}."""

    async def test_unknown_ticket_returns_404(self, client):
        """GET for a ticket that was never saved returns 404."""
        resp = await client.get('/api/requirements/AI-999')
        assert resp.status == 404
        data = await resp.json()
        assert 'error' in data
        assert data['ticket_key'] == 'AI-999'

    async def test_get_returns_all_fields(self, client):
        """GET after PUT returns all required fields."""
        # First PUT to create a requirement
        payload = {
            'edited_description': 'Show current requirement instructions.',
            'title': 'View Requirements',
            'description': 'Original Linear description',
            'spec_text': 'App spec text here',
            'sync_to_linear': False,
        }
        put_resp = await client.put(
            '/api/requirements/AI-90',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert put_resp.status == 200

        # Now GET
        resp = await client.get('/api/requirements/AI-90')
        assert resp.status == 200
        data = await resp.json()

        assert data['ticket_key'] == 'AI-90'
        assert data['title'] == 'View Requirements'
        assert data['description'] == 'Original Linear description'
        assert data['spec_text'] == 'App spec text here'
        assert data['edited_description'] == 'Show current requirement instructions.'
        assert data['sync_to_linear'] is False
        assert 'last_edited' in data
        assert 'linear_synced' in data
        assert 'timestamp' in data

    async def test_get_content_type_is_json(self, client):
        """GET response Content-Type is application/json."""
        # PUT first so it exists
        await client.put(
            '/api/requirements/AI-100',
            data=json.dumps({'edited_description': 'test'}),
            headers={'Content-Type': 'application/json'},
        )
        resp = await client.get('/api/requirements/AI-100')
        assert resp.status == 200
        assert 'application/json' in resp.content_type

    async def test_get_legacy_cache_promoted(self, client):
        """GET on a legacy-cached ticket (simple string) returns 200 with promoted data."""
        # Manually seed the legacy cache (simulating old data)
        rest_module._requirements_cache['AI-LEGACY'] = 'Old plain-text requirement'

        resp = await client.get('/api/requirements/AI-LEGACY')
        assert resp.status == 200
        data = await resp.json()
        assert data['ticket_key'] == 'AI-LEGACY'
        assert data['edited_description'] == 'Old plain-text requirement'
        # requirements compat field
        assert data['requirements'] == 'Old plain-text requirement'


# ---------------------------------------------------------------------------
# PUT /api/requirements/{ticket_key}
# ---------------------------------------------------------------------------

class TestPutRequirement:
    """Tests for PUT /api/requirements/{ticket_key}."""

    async def test_put_saves_edited_description(self, client):
        """PUT with edited_description saves correctly."""
        payload = {'edited_description': 'New requirement text.'}
        resp = await client.put(
            '/api/requirements/AI-91',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'success'
        assert data['ticket_key'] == 'AI-91'
        assert 'requirement' in data

        # Verify stored
        stored = rest_module._requirements_store.get('AI-91')
        assert stored is not None
        assert stored['edited_description'] == 'New requirement text.'

    async def test_put_legacy_requirements_field(self, client):
        """PUT with legacy 'requirements' field is accepted and stored."""
        payload = {'requirements': 'Legacy format text.'}
        resp = await client.put(
            '/api/requirements/AI-LEGACY2',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        stored = rest_module._requirements_store.get('AI-LEGACY2')
        assert stored['edited_description'] == 'Legacy format text.'

    async def test_put_missing_field_returns_400(self, client):
        """PUT without requirements or edited_description returns 400."""
        payload = {'title': 'Only title, no text'}
        resp = await client.put(
            '/api/requirements/AI-BAD',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data

    async def test_put_invalid_json_returns_400(self, client):
        """PUT with malformed JSON returns 400."""
        resp = await client.put(
            '/api/requirements/AI-BAD2',
            data='not valid json',
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400

    async def test_put_overwrites_existing(self, client):
        """PUT overwrites a previously stored requirement."""
        await client.put(
            '/api/requirements/AI-UPDATE',
            data=json.dumps({'edited_description': 'First version'}),
            headers={'Content-Type': 'application/json'},
        )
        await client.put(
            '/api/requirements/AI-UPDATE',
            data=json.dumps({'edited_description': 'Second version'}),
            headers={'Content-Type': 'application/json'},
        )

        resp = await client.get('/api/requirements/AI-UPDATE')
        data = await resp.json()
        assert data['edited_description'] == 'Second version'

    async def test_put_sync_to_linear_toggle_persists(self, client):
        """PUT with sync_to_linear=True is persisted and returned by GET."""
        payload = {
            'edited_description': 'Requirement to sync',
            'sync_to_linear': True,
        }
        await client.put(
            '/api/requirements/AI-SYNC',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )

        resp = await client.get('/api/requirements/AI-SYNC')
        data = await resp.json()
        assert data['sync_to_linear'] is True

    async def test_put_stores_last_edited_timestamp(self, client):
        """PUT stores last_edited timestamp."""
        payload = {'edited_description': 'Requirement with timestamp'}
        await client.put(
            '/api/requirements/AI-TS',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )

        stored = rest_module._requirements_store['AI-TS']
        assert stored['last_edited'] is not None
        # Validate it looks like an ISO timestamp
        assert 'T' in stored['last_edited']

    async def test_put_stores_all_optional_fields(self, client):
        """PUT stores title, description, spec_text."""
        payload = {
            'edited_description': 'Main content',
            'title': 'AI-90 Ticket Title',
            'description': 'Linear description',
            'spec_text': 'From app_spec.txt',
        }
        await client.put(
            '/api/requirements/AI-FULL',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )

        stored = rest_module._requirements_store['AI-FULL']
        assert stored['title'] == 'AI-90 Ticket Title'
        assert stored['description'] == 'Linear description'
        assert stored['spec_text'] == 'From app_spec.txt'

    async def test_put_too_long_returns_400(self, client):
        """PUT with text > 50000 chars returns 400."""
        payload = {'edited_description': 'x' * 50_001}
        resp = await client.put(
            '/api/requirements/AI-LONG',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# GET after PUT round-trip
# ---------------------------------------------------------------------------

class TestGetAfterPut:
    """Verify that GET returns exactly what was PUT."""

    async def test_get_returns_updated_description_after_put(self, client):
        """GET after PUT returns the updated description."""
        original = 'Original requirement text.'
        updated = 'Updated requirement text after edit.'

        await client.put(
            '/api/requirements/AI-RT',
            data=json.dumps({'edited_description': original}),
            headers={'Content-Type': 'application/json'},
        )
        await client.put(
            '/api/requirements/AI-RT',
            data=json.dumps({'edited_description': updated}),
            headers={'Content-Type': 'application/json'},
        )

        resp = await client.get('/api/requirements/AI-RT')
        data = await resp.json()
        assert data['edited_description'] == updated

    async def test_get_legacy_compat_field_matches_edited_description(self, client):
        """GET requirements field equals edited_description for backwards compat."""
        await client.put(
            '/api/requirements/AI-COMPAT',
            data=json.dumps({'edited_description': 'Compat text.'}),
            headers={'Content-Type': 'application/json'},
        )
        resp = await client.get('/api/requirements/AI-COMPAT')
        data = await resp.json()
        assert data['requirements'] == data['edited_description']


# ---------------------------------------------------------------------------
# POST /api/requirements/{ticket_key}/sync
# ---------------------------------------------------------------------------

class TestSyncRequirement:
    """Tests for POST /api/requirements/{ticket_key}/sync."""

    async def test_sync_unknown_ticket_returns_404(self, client):
        """Sync on unknown ticket returns 404."""
        resp = await client.post('/api/requirements/AI-NOSYNC/sync')
        assert resp.status == 404
        data = await resp.json()
        assert 'error' in data

    async def test_sync_marks_linear_synced_true(self, client):
        """POST sync marks linear_synced=True on the stored requirement."""
        # Create requirement first
        await client.put(
            '/api/requirements/AI-TOSYNC',
            data=json.dumps({'edited_description': 'Ready to sync.', 'sync_to_linear': False}),
            headers={'Content-Type': 'application/json'},
        )

        resp = await client.post('/api/requirements/AI-TOSYNC/sync')
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'success'
        assert data['linear_synced'] is True
        assert data['ticket_key'] == 'AI-TOSYNC'

        # Verify in store
        stored = rest_module._requirements_store['AI-TOSYNC']
        assert stored['linear_synced'] is True
        assert stored['sync_to_linear'] is True

    async def test_sync_response_has_timestamp(self, client):
        """POST sync response includes a timestamp."""
        await client.put(
            '/api/requirements/AI-SYNCTS',
            data=json.dumps({'edited_description': 'Some text'}),
            headers={'Content-Type': 'application/json'},
        )
        resp = await client.post('/api/requirements/AI-SYNCTS/sync')
        data = await resp.json()
        assert 'timestamp' in data
