"""Tests for helix_studio.services.crew_ai (unit tests)."""

from __future__ import annotations

import pytest

from helix_studio.services.crew_ai import (
    PRESET_TEAMS,
    VRAMBudget,
    estimate_model_size,
    list_preset_teams,
)


class TestVRAMBudget:
    def test_initial_available(self):
        budget = VRAMBudget(total_gb=24.0, reserved_gb=2.0)
        assert budget.available_gb == 22.0

    def test_can_load_within_budget(self):
        budget = VRAMBudget(total_gb=24.0, reserved_gb=2.0)
        assert budget.can_load("gemma3:27b", 16.0) is True

    def test_cannot_load_over_budget(self):
        budget = VRAMBudget(total_gb=24.0, reserved_gb=2.0)
        assert budget.can_load("big_model", 30.0) is False

    def test_register_and_available(self):
        budget = VRAMBudget(total_gb=24.0, reserved_gb=2.0)
        budget.register("gemma3:27b", 16.0)
        assert budget.available_gb == 6.0

    def test_unregister(self):
        budget = VRAMBudget(total_gb=24.0, reserved_gb=2.0)
        budget.register("model", 10.0)
        budget.unregister("model")
        assert budget.available_gb == 22.0

    def test_summary(self):
        budget = VRAMBudget(total_gb=96.0, reserved_gb=2.0)
        budget.register("gemma3:27b", 16.0)
        s = budget.summary()
        assert s["total_gb"] == 96.0
        assert s["used_gb"] == 16.0
        assert "gemma3:27b" in s["loaded_models"]


class TestEstimateModelSize:
    def test_known_model(self):
        assert estimate_model_size("gemma3:27b") == 16.0

    def test_parameter_based_120b(self):
        assert estimate_model_size("custom:120b") == 75.0

    def test_parameter_based_8b(self):
        assert estimate_model_size("custom:8b") == 6.0

    def test_unknown_default(self):
        assert estimate_model_size("totally_unknown") == 10.0


class TestPresetTeams:
    def test_all_teams_exist(self):
        assert "dev_team" in PRESET_TEAMS
        assert "research_team" in PRESET_TEAMS
        assert "writing_team" in PRESET_TEAMS

    def test_dev_team_has_agents(self):
        assert len(PRESET_TEAMS["dev_team"]) >= 2

    def test_list_preset_teams(self):
        teams = list_preset_teams()
        assert "dev_team" in teams
        for agent in teams["dev_team"]:
            assert "name" in agent
            assert "role" in agent
            assert "model" in agent
