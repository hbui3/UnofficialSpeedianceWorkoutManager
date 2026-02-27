"""
Unit tests for api_client.py — no real API calls needed.
All HTTP calls are mocked.
"""
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Make sure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from api_client import SpeedianceClient


def _make_client():
    """Return a client with fake credentials so methods don't bail early."""
    client = SpeedianceClient.__new__(SpeedianceClient)
    client.credentials = {"user_id": "test_user", "token": "test_token", "region": "Global", "unit": 0, "custom_instruction": ""}
    client.host = "api2.speediance.com"
    client.base_url = "https://api2.speediance.com"
    client.last_debug_info = {}
    client.library_cache = None
    client.session = MagicMock()
    return client


def _mock_save_response():
    """A successful save response mock."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"code": 0, "message": "Success", "data": {"id": 999, "code": "TEST001"}}
    return resp


def _make_detail_response(group_id, variant_id, is_unilateral=False):
    """Builds a fake exercise detail response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": {
            "id": group_id,
            "isLeftRight": 1 if is_unilateral else 0,
            "actionLibraryList": [{"id": variant_id}]
        }
    }
    return resp


def _make_batch_response(group_ids, variant_offset=1000):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": [
            {
                "id": gid,
                "actionLibraryList": [{"id": gid + variant_offset}]
            }
            for gid in group_ids
        ]
    }
    return resp


class TestSaveWorkoutWeights(unittest.TestCase):

    def _run_save(self, exercises, group_ids=None, unilateral_flags=None):
        """
        Runs save_workout with mocked network calls.
        Returns the JSON payload sent to the POST endpoint.
        """
        client = _make_client()

        if group_ids is None:
            group_ids = list({ex['groupId'] for ex in exercises})
        if unilateral_flags is None:
            unilateral_flags = {gid: False for gid in group_ids}

        # Mock get_batch_details
        client.get_batch_details = MagicMock(return_value=[
            {"id": gid, "actionLibraryList": [{"id": gid + 1000}]}
            for gid in group_ids
        ])

        # Mock is_exercise_unilateral
        client.is_exercise_unilateral = MagicMock(
            side_effect=lambda gid: unilateral_flags.get(gid, False)
        )

        # Capture the POST payload
        captured = {}
        def fake_request(method, url, **kwargs):
            if method == 'POST':
                captured['payload'] = kwargs.get('json', {})
            return _mock_save_response()

        client._request = MagicMock(side_effect=fake_request)

        client.save_workout("Test Workout", exercises)
        return captured.get('payload', {})

    def _get_action(self, payload, group_id):
        for a in payload.get('actionLibraryList', []):
            if a['groupId'] == group_id:
                return a
        return None

    # ------------------------------------------------------------------
    # Weight conversion tests
    # ------------------------------------------------------------------

    def test_custom_preset_weights_field_used(self):
        """Custom preset (-1) must populate 'weights', leave counterweight2 empty."""
        exercises = [{
            'groupId': 1,
            'variant_id': 1001,
            'preset_id': -1,
            'sets': [{'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'}]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 1)
        self.assertIsNotNone(action)
        self.assertNotEqual(action['weights'], '')
        self.assertEqual(action['counterweight2'], '')

    def test_custom_preset_weight_multiplied_by_2_2(self):
        """20 kg in custom mode → API weight field = '44.0' (20 * 2.2)."""
        exercises = [{
            'groupId': 1,
            'variant_id': 1001,
            'preset_id': -1,
            'sets': [{'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'}]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 1)
        self.assertEqual(action['weights'], '44.0')

    def test_half_kg_weight_converted_correctly(self):
        """3.5 kg → API weight = '7.7' (3.5 * 2.2)."""
        exercises = [{
            'groupId': 1,
            'variant_id': 1001,
            'preset_id': -1,
            'sets': [{'reps': 10, 'weight': 3.5, 'mode': 1, 'rest': 60, 'unit': 'reps'}]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 1)
        self.assertEqual(action['weights'], '7.7')

    def test_rm_preset_uses_counterweight2(self):
        """Gain Muscle preset (1) → counterweight2 has RM values, weights has dummy '3.5'."""
        exercises = [{
            'groupId': 2,
            'variant_id': 2001,
            'preset_id': 1,
            'sets': [
                {'reps': 10, 'weight': 12, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 8, 'weight': 13, 'mode': 1, 'rest': 60, 'unit': 'reps'},
            ]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 2)
        self.assertEqual(action['weights'], '3.5,3.5')
        self.assertEqual(action['counterweight2'], '12,13')

    def test_multiple_sets_weight_csv(self):
        """Multiple sets → weights field is comma-separated."""
        exercises = [{
            'groupId': 1,
            'variant_id': 1001,
            'preset_id': -1,
            'sets': [
                {'reps': 10, 'weight': 10.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 8,  'weight': 15.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 6,  'weight': 20.0, 'mode': 2, 'rest': 90, 'unit': 'reps'},
            ]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 1)
        self.assertEqual(action['weights'], '22.0,33.0,44.0')

    # ------------------------------------------------------------------
    # Unilateral L/R tests
    # ------------------------------------------------------------------

    def test_bilateral_leftright_all_zeros(self):
        """Bilateral exercise → leftRight = '0,0,0'."""
        exercises = [{
            'groupId': 10,
            'variant_id': 10001,
            'preset_id': -1,
            'sets': [
                {'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
            ]
        }]
        payload = self._run_save(exercises, unilateral_flags={10: False})
        action = self._get_action(payload, 10)
        self.assertEqual(action['leftRight'], '0,0,0')

    def test_unilateral_leftright_alternates_1_2(self):
        """Unilateral 4 sets (L1,R1,L2,R2) → leftRight = '1,2,1,2'."""
        exercises = [{
            'groupId': 20,
            'variant_id': 20001,
            'preset_id': -1,
            'sets': [
                {'reps': 10, 'weight': 6.0, 'mode': 1, 'rest': 45, 'unit': 'reps'},
                {'reps': 10, 'weight': 6.0, 'mode': 1, 'rest': 45, 'unit': 'reps'},
                {'reps': 8,  'weight': 7.0, 'mode': 2, 'rest': 60, 'unit': 'reps'},
                {'reps': 8,  'weight': 7.0, 'mode': 2, 'rest': 60, 'unit': 'reps'},
            ]
        }]
        payload = self._run_save(exercises, unilateral_flags={20: True})
        action = self._get_action(payload, 20)
        self.assertEqual(action['leftRight'], '1,2,1,2')

    # ------------------------------------------------------------------
    # CSV field correctness
    # ------------------------------------------------------------------

    def test_reps_modes_rest_csv(self):
        """setsAndReps, sportMode, breakTime2 are built correctly."""
        exercises = [{
            'groupId': 1,
            'variant_id': 1001,
            'preset_id': -1,
            'sets': [
                {'reps': 10, 'weight': 20.0, 'mode': 1, 'rest': 60, 'unit': 'reps'},
                {'reps': 8,  'weight': 14.0, 'mode': 2, 'rest': 90, 'unit': 'reps'},
                {'reps': 12, 'weight': 10.0, 'mode': 3, 'rest': 45, 'unit': 'reps'},
            ]
        }]
        payload = self._run_save(exercises)
        action = self._get_action(payload, 1)
        self.assertEqual(action['setsAndReps'], '10,8,12')
        self.assertEqual(action['sportMode'], '1,2,3')
        self.assertEqual(action['breakTime2'], '60,90,45')

    def test_preset_id_stored_in_action(self):
        """templatePresetId is passed through correctly."""
        for preset_id in [-1, 1, 3, 5]:
            exercises = [{
                'groupId': 1,
                'variant_id': 1001,
                'preset_id': preset_id,
                'sets': [{'reps': 10, 'weight': 10, 'mode': 1, 'rest': 60, 'unit': 'reps'}]
            }]
            payload = self._run_save(exercises)
            action = self._get_action(payload, 1)
            self.assertEqual(action['templatePresetId'], preset_id, f"preset_id={preset_id} not preserved")


class TestLbsKgMath(unittest.TestCase):
    """
    Tests for the conversion math used by the frontend (extracted as pure Python).
    These mirror what workout-logic.js does so we can verify correctness.
    """

    def lbs_to_kg_ui(self, lbs):
        """Frontend: lbs/2.2 rounded to nearest 0.5 kg."""
        kg = lbs / 2.2
        return round(kg * 2) / 2

    def kg_to_lbs_ui(self, kg):
        """Frontend reload: kg * 2.2 rounded to nearest integer lb."""
        return round(kg * 2.2)

    def test_100_lbs_round_trip(self):
        kg = self.lbs_to_kg_ui(100)
        lbs_back = self.kg_to_lbs_ui(kg)
        self.assertAlmostEqual(lbs_back, 100, delta=1)

    def test_55_lbs_round_trip(self):
        kg = self.lbs_to_kg_ui(55)
        lbs_back = self.kg_to_lbs_ui(kg)
        self.assertAlmostEqual(lbs_back, 55, delta=1)

    def test_220_lbs_round_trip(self):
        kg = self.lbs_to_kg_ui(220)
        lbs_back = self.kg_to_lbs_ui(kg)
        self.assertAlmostEqual(lbs_back, 220, delta=2)

    def test_half_kg_to_api(self):
        """3.5 kg → API weight ≈ 7.7."""
        api_w = 3.5 * 2.2
        self.assertAlmostEqual(api_w, 7.7, places=1)

    def test_clamp_to_min(self):
        """Value below min is clamped to min."""
        def clamp_step(val, min_w, max_w, step):
            val = max(min_w, min(max_w, val))
            return round(val / step) * step
        self.assertEqual(clamp_step(3.0, 3.5, 100, 0.5), 3.5)

    def test_round_to_step(self):
        """Value is snapped to nearest step."""
        def clamp_step(val, min_w, max_w, step):
            val = max(min_w, min(max_w, val))
            return round(val / step) * step
        self.assertAlmostEqual(clamp_step(5.3, 3.5, 100, 0.5), 5.5)
        self.assertAlmostEqual(clamp_step(5.1, 3.5, 100, 0.5), 5.0)

    def test_integer_step_unchanged(self):
        """Integer step still works normally."""
        def clamp_step(val, min_w, max_w, step):
            val = max(min_w, min(max_w, val))
            return round(val / step) * step
        self.assertEqual(clamp_step(13, 9, 13, 1), 13)
        self.assertEqual(clamp_step(8, 9, 13, 1), 9)


if __name__ == '__main__':
    unittest.main(verbosity=2)
