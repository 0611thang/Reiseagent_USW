"""
Automatisierte Tests für den Flight-Check über den LLM-Orchestrator.
"""

import copy
import os
import tempfile
import unittest
from unittest.mock import patch

import graph
import store
from agents import coordinator, monitoring


def _activity(
        activity_id: str,
        name: str,
        cost: float = 20.0,
) -> dict:
    return {
        "id": activity_id,
        "name": name,
        "category": "museum",
        "description": name,
        "location": {
            "name": "Berlin",
            "area": "Mitte",
            "lat": None,
            "lng": None,
        },
        "estimated_cost_per_person": cost,
        "estimated_cost_total": cost,
        "duration_minutes": 90,
        "indoor_outdoor": "indoor",
        "tags": ["museum"],
        "reasoning": "Testaktivität",
        "score": None,
        "source": "test",
    }


def _active_plan() -> dict:
    return {
        "id": "active-plan-1",
        "request": {},
        "days": [{
            "day_number": 1,
            "title": "Ankunftstag",
            "date": "2026-07-20",
            "weather": None,
            "time_slots": [{
                "id": "slot-1",
                "start_time": "14:00",
                "end_time": "15:30",
                "activity": _activity(
                    "old-museum",
                    "Altes Museum",
                ),
                "notes": None,
            }],
        }],
        "budget_summary": {
            "budget_total": 500.0,
            "planned_total": 20.0,
            "remaining": 480.0,
            "currency": "EUR",
            "per_person_total": 20.0,
            "categories": [],
            "status": "within_budget",
        },
        "status": "active",
        "created_at": "2026-07-01T10:00:00",
        "updated_at": "2026-07-01T10:00:00",
    }


def _request() -> dict:
    return {
        "destination": "Berlin",
        "duration_days": 1,
        "budget_total": 500.0,
        "currency": "EUR",
        "number_of_people": 1,
        "travel_type": "solo",
        "interests": ["Museen"],
        "flight_number": "LH123",
        "departure_date": "2026-07-20",
    }


def _flight_updates(delay: int = 45) -> dict:
    return {
        "source": "mock",
        "found": True,
        "flight_number": "LH123",
        "status": "delayed",
        "scheduled_arrival": "2026-07-20T12:00:00",
        "estimated_arrival": "2026-07-20T12:45:00",
        "departure_delay_minutes": delay,
        "arrival_delay_minutes": delay,
        "delay_minutes": delay,
    }


class FlightOrchestratorTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = store.DB_PATH

        store.DB_PATH = os.path.join(
            self.temp_dir.name,
            "trips.db",
        )

        store.init_db()

    def tearDown(self):
        store.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _create_stored_trip(self) -> dict:
        trip = store.create_trip(_request())

        return store.update_trip(
            trip["id"],
            {
                "active_plan": _active_plan(),
            },
        )

    def test_graph_proposal_mode_uses_replan_without_external_side_effects(
            self,
    ):
        trip = {
            "id": "test-trip",
            "request": _request(),
            "active_plan": _active_plan(),
            "proposals": [],
            "agent_insights": [],
            "chat_messages": [],
        }

        replacement = _activity(
            "new-museum",
            "Neues Museum",
            cost=25.0,
        )

        with (
            patch.object(
                graph.llm,
                "call_tools",
                return_value=(
                        "tool",
                        "replan_day",
                        {},
                ),
            ),
            patch.object(
                coordinator.places_provider,
                "get_places",
                return_value=[replacement],
            ),
            patch.object(
                coordinator,
                "sync_full_plan_to_calendar",
            ) as sync_mock,
            patch.object(
                coordinator,
                "send_plan_update",
            ) as telegram_update_mock,
        ):
            result = graph.run_chat(
                trip,
                (
                    "Flug LH123 hat 45 Minuten Verspätung. "
                    "Bitte plane Tag 1 neu."
                ),
                proposal_mode=True,
                include_metadata=True,
            )

        self.assertEqual(
            "replan_day",
            result["tool_name"],
        )

        self.assertEqual(
            "Neues Museum",
            trip["active_plan"]["days"][0]
            ["time_slots"][0]["activity"]["name"],
        )

        self.assertNotIn(
            "_proposal_mode",
            trip,
        )

        sync_mock.assert_not_called()
        telegram_update_mock.assert_not_called()

    def test_monitoring_builds_orchestrator_proposal_and_keeps_active_plan_unchanged(
            self,
    ):
        trip = self._create_stored_trip()
        original_plan = copy.deepcopy(trip["active_plan"])

        captured = {}

        def fake_run_chat(
                working_trip,
                message,
                **kwargs,
        ):
            captured["message"] = message
            captured["kwargs"] = kwargs

            working_trip["active_plan"]["days"][0]["time_slots"][0][
                "activity"
            ] = _activity(
                "smart-alternative",
                "Abendmuseum",
                cost=30.0,
            )

            return {
                "tool_name": "replan_day",
                "reply": {
                    "message": "Tag 1 wurde sinnvoll neu geplant.",
                },
            }

        with (
            patch.object(
                monitoring,
                "_call_flight_provider",
                return_value=_flight_updates(),
            ) as provider_mock,
            patch.object(
                monitoring.graph,
                "run_chat",
                side_effect=fake_run_chat,
            ) as graph_mock,
            patch.object(
                monitoring,
                "send_flight_delay_proposal",
                return_value=True,
            ) as telegram_mock,
        ):
            result = monitoring._refresh_flights(trip)

        self.assertEqual(
            1,
            result["proposals_created"],
        )

        self.assertTrue(result["telegram_sent"])
        self.assertFalse(result["fallback_used"])

        self.assertEqual(
            "llm_orchestrator",
            result["proposal_source"],
        )

        provider_mock.assert_called_once_with(
            _request(),
            use_mock=False,
        )

        graph_mock.assert_called_once()
        telegram_mock.assert_called_once()

        self.assertIn(
            "LH123",
            captured["message"],
        )

        self.assertIn(
            "45 Minuten",
            captured["message"],
        )

        self.assertIn(
            "Tag 1",
            captured["message"],
        )

        self.assertEqual(
            True,
            captured["kwargs"]["proposal_mode"],
        )

        self.assertEqual(
            True,
            captured["kwargs"]["include_metadata"],
        )

        saved = store.get_trip(trip["id"])

        # Der aktive Plan darf vor der Annahme nicht geändert worden sein.
        self.assertEqual(
            original_plan,
            saved["active_plan"],
        )

        self.assertEqual(
            45,
            saved["last_notified_flight_delay_minutes"],
        )

        self.assertEqual(
            1,
            len(saved["proposals"]),
        )

        proposal = saved["proposals"][0]

        self.assertEqual(
            "flight_delay",
            proposal["trigger"],
        )

        self.assertEqual(
            "llm_orchestrator",
            proposal["proposal_source"],
        )

        self.assertEqual(
            "Abendmuseum",
            proposal["proposed_plan"]["days"][0]
            ["time_slots"][0]["activity"]["name"],
        )

        self.assertTrue(proposal["changes"])

    def test_monitoring_uses_legacy_shift_when_orchestrator_fails(
            self,
    ):
        trip = self._create_stored_trip()

        with (
            patch.object(
                monitoring,
                "_call_flight_provider",
                return_value=_flight_updates(),
            ),
            patch.object(
                monitoring.graph,
                "run_chat",
                side_effect=RuntimeError(
                    "LLM nicht erreichbar"
                ),
            ),
            patch.object(
                monitoring,
                "send_flight_delay_proposal",
                return_value=True,
            ),
        ):
            result = monitoring._refresh_flights(trip)

        self.assertEqual(
            1,
            result["proposals_created"],
        )

        self.assertTrue(
            result["fallback_used"],
        )

        self.assertEqual(
            "legacy_shift_fallback",
            result["proposal_source"],
        )

        proposal = store.get_trip(
            trip["id"]
        )["proposals"][0]

        self.assertEqual(
            "legacy_shift_fallback",
            proposal["proposal_source"],
        )

        self.assertIn(
            "LLM nicht erreichbar",
            proposal["orchestrator_error"],
        )

        shifted_slot = (
            proposal["proposed_plan"]["days"][0]["time_slots"][0]
        )

        self.assertEqual(
            "14:45",
            shifted_slot["start_time"],
        )

        self.assertEqual(
            "16:15",
            shifted_slot["end_time"],
        )

    def test_orchestrator_is_not_called_again_for_pending_same_delay(
            self,
    ):
        trip = self._create_stored_trip()

        def fake_run_chat(
                working_trip,
                _message,
                **_kwargs,
        ):
            working_trip["active_plan"]["days"][0]["time_slots"][0][
                "activity"
            ] = _activity(
                "smart-alternative",
                "Abendmuseum",
            )

            return {
                "tool_name": "replan_day",
                "reply": {
                    "message": "Tag 1 wurde neu geplant.",
                },
            }

        with (
            patch.object(
                monitoring,
                "_call_flight_provider",
                return_value=_flight_updates(),
            ),
            patch.object(
                monitoring.graph,
                "run_chat",
                side_effect=fake_run_chat,
            ),
            patch.object(
                monitoring,
                "send_flight_delay_proposal",
                return_value=True,
            ),
        ):
            first_result = monitoring._refresh_flights(trip)

        self.assertEqual(
            1,
            first_result["proposals_created"],
        )

        saved_trip = store.get_trip(trip["id"])

        with (
            patch.object(
                monitoring,
                "_call_flight_provider",
                return_value=_flight_updates(),
            ),
            patch.object(
                monitoring.graph,
                "run_chat",
            ) as graph_mock,
            patch.object(
                monitoring,
                "send_flight_delay_proposal",
            ) as telegram_mock,
        ):
            second_result = monitoring._refresh_flights(
                saved_trip
            )

        self.assertEqual(
            0,
            second_result["proposals_created"],
        )

        graph_mock.assert_not_called()
        telegram_mock.assert_not_called()

    def test_controlled_mock_delay_can_be_requested_without_real_api(
            self,
    ):
        with patch.dict(
                os.environ,
                {
                    "MOCK_FLIGHT_DELAY_MINUTES": "45",
                },
                clear=False,
        ):
            updates = monitoring._call_flight_provider(
                _request(),
                use_mock=True,
            )

        self.assertEqual(
            "mock",
            updates["source"],
        )

        self.assertEqual(
            45,
            updates["delay_minutes"],
        )

        self.assertEqual(
            "delayed",
            updates["status"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)