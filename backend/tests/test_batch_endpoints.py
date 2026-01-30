"""
Integration tests for batch upsert endpoints.

Tests concurrent requests, duplicate external IDs, atomic transaction behavior,
and edge cases for /api/v1/games/batch and /api/v1/teams/batch.
"""

import pytest
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch("backend.api.main.get_supabase") as mock_get_sb, \
         patch("backend.api.supabase_client.get_supabase") as mock_get_sb2:
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_get_sb2.return_value = mock_sb

        # Setup upsert chain for teams
        mock_upsert = MagicMock()
        mock_sb.table.return_value.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = MagicMock(
            data=[{"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}]
        )

        from backend.api.main import app
        yield TestClient(app), mock_sb


@pytest.fixture
def mock_upsert_game():
    """Mock the upsert_game function from supabase_client."""
    with patch("backend.api.main.upsert_game") as mock:
        mock.return_value = {"id": "11111111-2222-3333-4444-555555555555"}
        yield mock


def _make_game_item(external_id="ext-001", home="Duke", away="UNC", date="2025-02-01"):
    return {
        "external_id": external_id,
        "home_team": home,
        "away_team": away,
        "date": date,
    }


def _make_team_item(name="Duke", conference="ACC"):
    return {"name": name, "conference": conference}


# =============================================================================
# TEST 1: Batch upsert with unique items succeeds and returns correct count
# =============================================================================

class TestBatchUpsertUniqueItems:
    def test_games_batch_unique_items_returns_correct_count(self, client, mock_upsert_game):
        test_client, mock_sb = client
        games = [
            _make_game_item("ext-001", "Duke", "UNC", "2025-02-01"),
            _make_game_item("ext-002", "Kansas", "Kentucky", "2025-02-01"),
            _make_game_item("ext-003", "Gonzaga", "UCLA", "2025-02-02"),
        ]

        response = test_client.post("/api/v1/games/batch", json={"games": games})

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
        assert len(data["results"]) == 3
        assert len(data["errors"]) == 0
        assert all(r["status"] == "updated" for r in data["results"])

    def test_teams_batch_unique_items_returns_correct_count(self, client):
        test_client, mock_sb = client
        teams = [
            _make_team_item("Duke", "ACC"),
            _make_team_item("Kansas", "Big 12"),
            _make_team_item("Gonzaga", "WCC"),
        ]

        response = test_client.post("/api/v1/teams/batch", json={"teams": teams})

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
        assert len(data["results"]) == 3
        assert len(data["errors"]) == 0


# =============================================================================
# TEST 2: Batch upsert with duplicate external_ids handles gracefully
# =============================================================================

class TestBatchUpsertDuplicateExternalIds:
    def test_games_duplicate_external_ids_no_crash(self, client, mock_upsert_game):
        """Duplicate external_ids in the same batch should not crash; each is processed."""
        test_client, mock_sb = client
        games = [
            _make_game_item("ext-dup", "Duke", "UNC", "2025-02-01"),
            _make_game_item("ext-dup", "Duke", "UNC", "2025-02-01"),
        ]

        response = test_client.post("/api/v1/games/batch", json={"games": games})

        assert response.status_code == 200
        data = response.json()
        # Both items processed (upsert handles dedup at DB level)
        assert len(data["results"]) == 2
        assert mock_upsert_game.call_count == 2

    def test_teams_duplicate_names_no_crash(self, client):
        """Duplicate team names in the same batch should not crash."""
        test_client, mock_sb = client
        teams = [
            _make_team_item("Duke", "ACC"),
            _make_team_item("Duke", "ACC"),
        ]

        response = test_client.post("/api/v1/teams/batch", json={"teams": teams})

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2


# =============================================================================
# TEST 3: Concurrent batch upserts don't create duplicates (threading)
# =============================================================================

class TestConcurrentBatchUpserts:
    def test_concurrent_game_batch_upserts(self, client, mock_upsert_game):
        """Concurrent batch requests should each complete without error."""
        test_client, mock_sb = client
        results = []
        errors = []

        def do_batch(ext_prefix):
            try:
                games = [_make_game_item(f"{ext_prefix}-{i}", f"Team{i}A", f"Team{i}B", "2025-02-01") for i in range(3)]
                resp = test_client.post("/api/v1/games/batch", json={"games": games})
                results.append(resp.json())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_batch, args=(f"batch-{t}",)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent requests raised errors: {errors}"
        assert len(results) == 3
        for r in results:
            assert r["updated"] == 3
            assert len(r["errors"]) == 0

    def test_concurrent_team_batch_upserts(self, client):
        """Concurrent team batch requests should each complete without error."""
        test_client, mock_sb = client
        results = []
        errors = []

        def do_batch(prefix):
            try:
                teams = [_make_team_item(f"{prefix}-Team{i}", "ACC") for i in range(3)]
                resp = test_client.post("/api/v1/teams/batch", json={"teams": teams})
                results.append(resp.json())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_batch, args=(f"batch-{t}",)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 3


# =============================================================================
# TEST 4: Partial failure reports partial success (not atomic rollback)
# =============================================================================

class TestPartialFailure:
    def test_games_partial_failure_reports_per_item(self, client):
        """If one item fails, others still succeed (partial success model)."""
        test_client, mock_sb = client
        call_count = 0

        def upsert_side_effect(game_data):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Simulated DB error on item 2")
            return {"id": f"uuid-{call_count}"}

        with patch("backend.api.main.upsert_game", side_effect=upsert_side_effect):
            games = [
                _make_game_item("ext-ok-1", "Duke", "UNC", "2025-02-01"),
                _make_game_item("ext-fail", "Bad", "Data", "2025-02-01"),
                _make_game_item("ext-ok-2", "Kansas", "Kentucky", "2025-02-01"),
            ]

            response = test_client.post("/api/v1/games/batch", json={"games": games})

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 2
        assert len(data["errors"]) == 1
        assert data["errors"][0]["index"] == 1
        assert "Simulated DB error" in data["errors"][0]["error"]
        assert len(data["results"]) == 3

    def test_teams_partial_failure_reports_per_item(self, client):
        """If one team upsert fails, others still succeed."""
        test_client, mock_sb = client
        call_count = 0

        original_upsert = mock_sb.table.return_value.upsert

        def upsert_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Simulated team DB error")
            mock_result = MagicMock()
            mock_result.execute.return_value = MagicMock(
                data=[{"id": f"team-uuid-{call_count}"}]
            )
            return mock_result

        mock_sb.table.return_value.upsert.side_effect = upsert_side_effect

        teams = [
            _make_team_item("Duke", "ACC"),
            _make_team_item("BadTeam", "BadConf"),
            _make_team_item("Kansas", "Big 12"),
        ]

        response = test_client.post("/api/v1/teams/batch", json={"teams": teams})

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 2
        assert len(data["errors"]) == 1
        assert data["errors"][0]["index"] == 1


# =============================================================================
# TEST 5: Empty batch returns appropriate response (validation error)
# =============================================================================

class TestEmptyBatch:
    def test_games_empty_batch_returns_error(self, client):
        """Empty games list should return an error (400 or 422)."""
        test_client, mock_sb = client

        response = test_client.post("/api/v1/games/batch", json={"games": []})

        assert response.status_code in (400, 422)

    def test_teams_empty_batch_returns_error(self, client):
        """Empty teams list should return an error (400 or 422)."""
        test_client, mock_sb = client

        response = test_client.post("/api/v1/teams/batch", json={"teams": []})

        assert response.status_code in (400, 422)

    def test_games_missing_body_returns_error(self, client):
        """Missing request body should return an error."""
        test_client, mock_sb = client

        response = test_client.post("/api/v1/games/batch", json={})

        assert response.status_code in (400, 422)

    def test_teams_missing_body_returns_error(self, client):
        """Missing request body should return an error."""
        test_client, mock_sb = client

        response = test_client.post("/api/v1/teams/batch", json={})

        assert response.status_code in (400, 422)
