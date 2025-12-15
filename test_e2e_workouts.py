import os
import time
import unittest
from copy import deepcopy

from api_client import SpeedianceClient


def _require_creds(client: SpeedianceClient) -> None:
    user_id = client.credentials.get("user_id")
    token = client.credentials.get("token")
    if not user_id or not token:
        raise unittest.SkipTest(
            "Missing credentials: set config.json or environment variables SPEEDIANCE_USER_ID and SPEEDIANCE_TOKEN."
        )


class TestWorkoutE2E(unittest.TestCase):
    """End-to-end tests against Speediance API.

    Notes:
    - These tests CREATE and DELETE workouts on your Speediance account.
    - Requires valid credentials in config.json (preferred) or env vars.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = SpeedianceClient()

        # Optional override via env
        env_uid = os.environ.get("SPEEDIANCE_USER_ID")
        env_tok = os.environ.get("SPEEDIANCE_TOKEN")
        if env_uid and env_tok:
            cls.client.credentials["user_id"] = env_uid
            cls.client.credentials["token"] = env_tok

        _require_creds(cls.client)

        # Ensure library cache is fresh
        cls.client.library_cache = None

        library = cls.client.get_library()
        if not library or len(library) < 2:
            raise unittest.SkipTest("Library empty/unavailable; cannot run E2E tests.")

        # Pick a couple exercise group IDs that have at least one variant (actionLibraryList)
        cls.group_ids = []
        cls.variant_by_group = {}

        for ex in library:
            if len(cls.group_ids) >= 2:
                break
            gid = int(ex.get("id"))
            try:
                detail = cls.client.get_exercise_detail(gid) or {}
                variants = detail.get("actionLibraryList") or []
                if not variants:
                    continue
                vid = variants[0].get("id")
                if not vid:
                    continue
                cls.group_ids.append(gid)
                cls.variant_by_group[gid] = int(vid)
            except Exception:
                continue

        if len(cls.group_ids) < 2:
            raise unittest.SkipTest("Could not find 2 exercises with variants; cannot run E2E tests.")

        # Find at least one unilateral exercise if possible (optional)
        cls.unilateral_group_id = None
        for ex in library[:80]:
            gid = int(ex.get("id"))
            try:
                if cls.client.is_exercise_unilateral(gid):
                    detail = cls.client.get_exercise_detail(gid) or {}
                    variants = detail.get("actionLibraryList") or []
                    if variants and variants[0].get("id"):
                        cls.unilateral_group_id = gid
                        cls.variant_by_group[gid] = int(variants[0]["id"])
                        break
            except Exception:
                continue

    def _create_payload_exercises(self, *, custom: bool = True):
        """Build the same structure create.html sends to /create."""

        def set_obj(reps, weight, mode, rest, unit="reps"):
            return {"reps": reps, "weight": weight, "mode": mode, "rest": rest, "unit": unit}

        gid1 = self.group_ids[0]
        gid2 = self.group_ids[1]

        ex1 = {
            "groupId": gid1,
            # IMPORTANT: use a real actionLibraryId (variant id)
            "variant_id": self.variant_by_group.get(gid1, gid1),
            "preset_id": -1 if custom else 1,
            "sets": [
                set_obj(10, 12, 1, 60),
                set_obj(8, 14, 2, 90),
                set_obj(12, 10, 3, 45),
            ],
        }

        ex2 = {
            "groupId": gid2,
            "variant_id": self.variant_by_group.get(gid2, gid2),
            "preset_id": -1 if custom else 3,
            "sets": [
                set_obj(15, 8, 1, 30),
                set_obj(12, 9, 2, 60),
            ],
        }

        exercises = [ex1, ex2]

        # Optional unilateral exercise: use 2 logical sets -> requires 4 entries (L/R)
        if self.unilateral_group_id:
            gid3 = self.unilateral_group_id
            ex3 = {
                "groupId": gid3,
                "variant_id": self.variant_by_group.get(gid3, gid3),
                "preset_id": -1 if custom else 1, # Use preset 1 for unilateral test if not custom
                "sets": [
                    set_obj(10, 6, 1, 45),
                    set_obj(10, 6, 1, 45),
                    set_obj(8, 7, 2, 60),
                    set_obj(8, 7, 2, 60),
                ],
            }
            exercises.append(ex3)

        return exercises

    def _find_latest_by_name(self, name: str):
        """Find a workout template (id, code) by exact name."""
        workouts = self.client.get_user_workouts() or []
        matches = [w for w in workouts if w.get("name") == name]
        if not matches:
            return None
        # Prefer most recent by id if present
        matches.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        return matches[0]

    def _extract_exercise_from_detail(self, detail, group_id=None, action_library_id=None, preset_id=None):
        """Pick a matching exercise entry from detail.actionLibraryList."""
        lst = detail.get("actionLibraryList") or []
        for item in lst:
            match = True
            if group_id is not None:
                if not (item.get("groupId") == group_id or item.get("actionLibraryId") == group_id):
                    match = False
            if match and action_library_id is not None:
                if item.get("actionLibraryId") != action_library_id:
                    match = False
            if match and preset_id is not None:
                if int(item.get("templatePresetId", -1)) != preset_id:
                    match = False
            
            if match:
                return item
        return None

    def _parse_csv_ints(self, s: str):
        if s is None or s == "":
            return []
        return [int(float(x)) for x in str(s).split(",") if str(x).strip() != ""]

    def _parse_csv_floats(self, s: str):
        if s is None or s == "":
            return []
        return [float(x) for x in str(s).split(",") if str(x).strip() != ""]

    def test_create_save_reload_custom_workout_matches(self):
        """Create a workout (custom KG), reload it, and compare key fields."""
        name = f"E2E_TEST_CUSTOM_{int(time.time())}"
        exercises = self._create_payload_exercises(custom=True)

        # Create
        resp = self.client.save_workout(name, deepcopy(exercises), template_id=None)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp.get("code"), 0, msg=f"Save failed: {resp}")

        # Find created workout and fetch detail
        created = self._find_latest_by_name(name)
        self.assertIsNotNone(created, "Workout not found after creation")
        code = created.get("code")
        self.assertTrue(code, f"Missing code in list response: {created}")

        detail = self.client.get_workout_detail(code)
        self.assertIsInstance(detail, dict)
        self.assertEqual(detail.get("name"), name)

        # Compare each exercise by groupId
        for ex in exercises:
            gid = int(ex["groupId"])
            expected_preset = int(ex.get("preset_id", -1))

            saved_ex = self._extract_exercise_from_detail(detail, group_id=gid)
            self.assertIsNotNone(saved_ex, f"Exercise group {gid} not present in detail")
            self.assertEqual(int(saved_ex.get("templatePresetId", -1)), expected_preset)

            # Parse reps
            reps_saved = self._parse_csv_ints(saved_ex.get("setsAndReps", ""))
            reps_expected = [int(s["reps"]) for s in ex["sets"]]

            is_unilateral = self.client.is_exercise_unilateral(gid)
            if is_unilateral:
                # API stores reps for each L/R entry; we send already expanded list
                self.assertEqual(reps_saved, reps_expected)
            else:
                self.assertEqual(reps_saved, reps_expected)

            # Parse modes and rest
            modes_saved = self._parse_csv_ints(saved_ex.get("sportMode", ""))
            rest_saved = self._parse_csv_ints(saved_ex.get("breakTime2", ""))
            modes_expected = [int(s["mode"]) for s in ex["sets"]]
            rest_expected = [int(s["rest"]) for s in ex["sets"]]
            self.assertEqual(modes_saved, modes_expected)
            self.assertEqual(rest_saved, rest_expected)

            # Weight mapping: for custom the API returns weights in KG (as strings/floats).
            self.assertEqual(saved_ex.get("counterweight2", ""), "")
            weights_saved = self._parse_csv_floats(saved_ex.get("weights", ""))
            weights_expected = [float(s["weight"]) for s in ex["sets"]]
            self.assertEqual(weights_saved, weights_expected)

        # Cleanup
        try:
            self.client.delete_workout(int(created.get("id")))
        except Exception:
            pass

    def test_create_save_reload_preset_workout_matches(self):
        """Create a workout with preset (RM), reload it, and compare key fields."""
        name = f"E2E_TEST_PRESET_{int(time.time())}"
        exercises = self._create_payload_exercises(custom=False)

        resp = self.client.save_workout(name, deepcopy(exercises), template_id=None)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp.get("code"), 0, msg=f"Save failed: {resp}")

        created = self._find_latest_by_name(name)
        self.assertIsNotNone(created, "Workout not found after creation")
        code = created.get("code")

        detail = self.client.get_workout_detail(code)
        self.assertEqual(detail.get("name"), name)

        for ex in exercises:
            gid = int(ex["groupId"])
            expected_preset = int(ex.get("preset_id"))
            saved_ex = self._extract_exercise_from_detail(detail, group_id=gid, preset_id=expected_preset)
            self.assertIsNotNone(saved_ex, f"Could not find exercise with gid={gid} and preset={expected_preset}")
            
            print(f"DEBUG: gid={gid} preset={expected_preset}")
            print(f"DEBUG: saved_ex keys: {saved_ex.keys()}")
            print(f"DEBUG: counterweight2: '{saved_ex.get('counterweight2')}'")
            print(f"DEBUG: weights: '{saved_ex.get('weights')}'")

            self.assertEqual(int(saved_ex.get("templatePresetId", -1)), expected_preset)

            reps_saved = self._parse_csv_ints(saved_ex.get("setsAndReps", ""))
            reps_expected = [int(s["reps"]) for s in ex["sets"]]
            self.assertEqual(reps_saved, reps_expected)

            modes_saved = self._parse_csv_ints(saved_ex.get("sportMode", ""))
            rest_saved = self._parse_csv_ints(saved_ex.get("breakTime2", ""))
            self.assertEqual(modes_saved, [int(s["mode"]) for s in ex["sets"]])
            self.assertEqual(rest_saved, [int(s["rest"]) for s in ex["sets"]])

            # Presets should store counterweight2 (RM). API may still return a dummy weights list (e.g. 3.5,3.5,3.5), so don't assert weights=="".
            cw_saved = self._parse_csv_ints(saved_ex.get("counterweight2", ""))
            cw_expected = [int(float(s["weight"])) for s in ex["sets"]]
            
            # If unilateral, the API might store 2 entries per set (L/R) even for presets?
            # Or maybe it doesn't expand counterweight2 for unilateral?
            # Let's check if we need to expand expected
            is_unilateral = self.client.is_exercise_unilateral(gid)
            if is_unilateral:
                 # Unilateral exercises seem to NOT duplicate counterweight2 in the response?
                 # OR they do?
                 # Let's just check if the values match either the raw list or the expanded list
                 cw_expected_expanded = []
                 for w in cw_expected:
                     cw_expected_expanded.extend([w, w])
                 
                 if cw_saved == cw_expected:
                     pass # OK
                 elif cw_saved == cw_expected_expanded:
                     pass # OK
                 else:
                     # Fail with useful message
                     self.assertEqual(cw_saved, cw_expected, f"Unilateral mismatch. Saved: {cw_saved}, Expected: {cw_expected} (or expanded: {cw_expected_expanded})")
            else:
                 self.assertEqual(cw_saved, cw_expected)

        # Cleanup
        try:
            self.client.delete_workout(int(created.get("id")))
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
