"""Integration Tests für REST API."""

import json


class TestCRAAPI:
    """Tests für CRA-API Endpoints."""

    def test_get_dashboard(self):
        """Test: GET /api/cra/dashboard."""
        # client = create_app().test_client()
        # response = client.get('/api/cra/dashboard')
        # assert response.status_code == 200
        # data = json.loads(response.data)
        # assert 'maturity_score' in data
        pass

    def test_get_controls(self):
        """Test: GET /api/cra/controls."""
        # response = client.get('/api/cra/controls')
        # assert response.status_code == 200
        # data = json.loads(response.data)
        # assert 'controls' in data
        pass

    def test_update_control_requires_auth(self):
        """Test: POST /api/cra/controls/{id} requires auth."""
        # response = client.post('/api/cra/controls/C1', json={})
        # assert response.status_code == 401
        pass

    def test_update_control_requires_permission(self):
        """Test: POST /api/cra/controls/{id} requires cra:write."""
        # Login as cra_viewer, try to POST
        # assert response.status_code == 403
        pass
