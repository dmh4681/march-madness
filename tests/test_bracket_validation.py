"""
Tests for tournament bracket endpoint input validation.

Tests Pydantic model validation for bracket management endpoints
and whitelist validation in supabase_client functions.
"""

import sys
import os
import pytest
from pydantic import ValidationError

# Add project root to path so we can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.main import (
    TournamentSeedInput,
    SetBracketRequest,
    BracketPickRequest,
    GeneratePicksRequest,
    VALID_REGIONS,
    VALID_ROUNDS,
)
from backend.api.supabase_client import (
    _validate_region,
    _validate_round,
    _sanitize_string,
    _validate_uuid,
)


# ============================================
# TournamentSeedInput validation
# ============================================


class TestTournamentSeedInput:
    def test_valid_seed(self):
        seed = TournamentSeedInput(
            team_name="Duke", seed=1, region="East"
        )
        assert seed.team_name == "Duke"
        assert seed.seed == 1
        assert seed.region == "East"
        assert seed.is_play_in is False

    def test_valid_seed_with_special_chars(self):
        seed = TournamentSeedInput(
            team_name="St. Mary's (CA)", seed=5, region="West"
        )
        assert seed.team_name == "St. Mary's (CA)"

    def test_valid_play_in(self):
        seed = TournamentSeedInput(
            team_name="Texas Southern", seed=16, region="South",
            is_play_in=True, play_in_matchup=1
        )
        assert seed.is_play_in is True
        assert seed.play_in_matchup == 1

    def test_invalid_team_name_injection(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            TournamentSeedInput(
                team_name="Duke; DROP TABLE teams;--", seed=1, region="East"
            )

    def test_empty_team_name(self):
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="", seed=1, region="East")

    def test_team_name_too_long(self):
        with pytest.raises(ValidationError):
            TournamentSeedInput(
                team_name="A" * 101, seed=1, region="East"
            )

    def test_invalid_seed_too_low(self):
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="Duke", seed=0, region="East")

    def test_invalid_seed_too_high(self):
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="Duke", seed=17, region="East")

    def test_invalid_region(self):
        with pytest.raises(ValidationError):
            TournamentSeedInput(
                team_name="Duke", seed=1, region="Northwest"
            )

    def test_all_valid_regions(self):
        for region in ["East", "West", "South", "Midwest"]:
            seed = TournamentSeedInput(
                team_name="Duke", seed=1, region=region
            )
            assert seed.region == region


# ============================================
# BracketPickRequest validation
# ============================================


class TestBracketPickRequest:
    VALID_UUID = "12345678-1234-1234-1234-123456789abc"

    def test_valid_pick(self):
        pick = BracketPickRequest(
            game_id=self.VALID_UUID,
            picked_team_id=self.VALID_UUID,
            confidence_score=0.75,
            reasoning="Strong KenPom edge"
        )
        assert pick.confidence_score == 0.75

    def test_valid_pick_minimal(self):
        pick = BracketPickRequest(
            game_id=self.VALID_UUID,
            picked_team_id=self.VALID_UUID
        )
        assert pick.confidence_score is None
        assert pick.reasoning is None

    def test_invalid_game_id(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            BracketPickRequest(
                game_id="not-a-uuid",
                picked_team_id=self.VALID_UUID
            )

    def test_invalid_team_id(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            BracketPickRequest(
                game_id=self.VALID_UUID,
                picked_team_id="bad-id"
            )

    def test_confidence_too_low(self):
        with pytest.raises(ValidationError):
            BracketPickRequest(
                game_id=self.VALID_UUID,
                picked_team_id=self.VALID_UUID,
                confidence_score=-0.1
            )

    def test_confidence_too_high(self):
        with pytest.raises(ValidationError):
            BracketPickRequest(
                game_id=self.VALID_UUID,
                picked_team_id=self.VALID_UUID,
                confidence_score=1.1
            )

    def test_reasoning_too_long(self):
        with pytest.raises(ValidationError):
            BracketPickRequest(
                game_id=self.VALID_UUID,
                picked_team_id=self.VALID_UUID,
                reasoning="X" * 1001
            )

    def test_confidence_boundary_values(self):
        for conf in [0.0, 0.5, 1.0]:
            pick = BracketPickRequest(
                game_id=self.VALID_UUID,
                picked_team_id=self.VALID_UUID,
                confidence_score=conf
            )
            assert pick.confidence_score == conf


# ============================================
# GeneratePicksRequest validation
# ============================================


class TestGeneratePicksRequest:
    def test_valid_request(self):
        req = GeneratePicksRequest(
            season=2025, region="East", round="sweet_16",
            provider="claude", force=False
        )
        assert req.season == 2025

    def test_valid_minimal(self):
        req = GeneratePicksRequest(season=2025)
        assert req.region is None
        assert req.round is None
        assert req.provider == "claude"
        assert req.force is False

    def test_invalid_region(self):
        with pytest.raises(ValidationError, match="Invalid region"):
            GeneratePicksRequest(season=2025, region="Northwest")

    def test_invalid_round(self):
        with pytest.raises(ValidationError, match="Invalid round"):
            GeneratePicksRequest(season=2025, round="quarterfinal")

    def test_all_valid_regions(self):
        for region in VALID_REGIONS:
            req = GeneratePicksRequest(season=2025, region=region)
            assert req.region == region

    def test_all_valid_rounds(self):
        for rnd in VALID_ROUNDS:
            req = GeneratePicksRequest(season=2025, round=rnd)
            assert req.round == rnd

    def test_season_too_low(self):
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=1999)

    def test_season_too_high(self):
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=2101)

    def test_invalid_provider(self):
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=2025, provider="chatgpt")

    def test_grok_provider(self):
        req = GeneratePicksRequest(season=2025, provider="grok")
        assert req.provider == "grok"


# ============================================
# SetBracketRequest validation
# ============================================


class TestSetBracketRequest:
    def _make_seeds(self, count=64):
        seeds = []
        regions = ["East", "West", "South", "Midwest"]
        for i in range(count):
            seeds.append(TournamentSeedInput(
                team_name=f"Team {i}",
                seed=(i % 16) + 1,
                region=regions[i % 4]
            ))
        return seeds

    def test_valid_bracket(self):
        req = SetBracketRequest(season=2025, seeds=self._make_seeds(64))
        assert len(req.seeds) == 64

    def test_valid_bracket_with_play_in(self):
        req = SetBracketRequest(season=2025, seeds=self._make_seeds(68))
        assert len(req.seeds) == 68

    def test_too_few_seeds(self):
        with pytest.raises(ValidationError):
            SetBracketRequest(season=2025, seeds=self._make_seeds(63))

    def test_too_many_seeds(self):
        with pytest.raises(ValidationError):
            SetBracketRequest(season=2025, seeds=self._make_seeds(69))


# ============================================
# supabase_client whitelist validation
# ============================================


class TestSupabaseClientValidation:
    def test_validate_region_valid(self):
        for region in ["East", "West", "South", "Midwest"]:
            assert _validate_region(region) == region

    def test_validate_region_invalid(self):
        with pytest.raises(ValueError, match="Invalid region"):
            _validate_region("Northwest")

    def test_validate_region_case_sensitive(self):
        with pytest.raises(ValueError):
            _validate_region("east")

    def test_validate_round_valid(self):
        for rnd in ["first_four", "round_64", "round_32", "sweet_16",
                     "elite_8", "final_4", "championship"]:
            assert _validate_round(rnd) == rnd

    def test_validate_round_invalid(self):
        with pytest.raises(ValueError, match="Invalid round"):
            _validate_round("quarterfinal")

    def test_validate_uuid_valid(self):
        result = _validate_uuid("12345678-1234-1234-1234-123456789abc")
        assert result == "12345678-1234-1234-1234-123456789abc"

    def test_validate_uuid_invalid(self):
        with pytest.raises(ValueError):
            _validate_uuid("not-a-uuid")

    def test_validate_uuid_empty(self):
        with pytest.raises(ValueError):
            _validate_uuid("")

    def test_sanitize_string_truncation(self):
        long_str = "A" * 500
        result = _sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_sanitize_string_null_bytes(self):
        result = _sanitize_string("hello\x00world")
        assert "\x00" not in result
        assert result == "helloworld"

    def test_sanitize_string_empty(self):
        assert _sanitize_string("") == ""
