"""Tests for map parsing and live mower pose handling."""

import importlib.util
import math
import unittest
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "navimow_plus" / "map_support.py"
)
_SPEC = importlib.util.spec_from_file_location("navimow_plus_map_support", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MAP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MAP)


class MapSupportTest(unittest.TestCase):
    def test_extract_map_geometry(self) -> None:
        raw = {
            "map_detail": {
                "id": 17,
                "name": "Garden",
                "area": "120.5",
                "map_width": 20,
                "map_height": 12,
                "sub_maps": [
                    {
                        "id": 3,
                        "name": "Front lawn",
                        "area": 42,
                        "elements": [
                            {
                                "type": "BOUNDARY",
                                "points": [[0, 0, 1], [10, 0, 1], [10, 8, 2]],
                                "mow_edge": 1,
                            },
                            {
                                "type": "CHARGING_PILE",
                                "position": [1.5, 2.5],
                                "direction": 1.2,
                            },
                        ],
                    }
                ],
                "obstacles": [{"points": [[2, 2], [3, 2], [3, 3]]}],
                "vision_off_areas": [{"points": [[4, 4], [5, 4], [5, 5]]}],
                "tunnels": [
                    {"id": 8, "points": [[10, 4], [12, 4]], "connection": [3, 4]}
                ],
            }
        }
        geometry = _MAP.extract_map_geometry(raw)
        self.assertIsNotNone(geometry)
        self.assertEqual(geometry["name"], "Garden")
        self.assertEqual(geometry["zones"][0]["polygon"][2], [10.0, 8.0])
        self.assertEqual(geometry["zones"][0]["boundary_flags"], [1, 1, 2])
        self.assertEqual(geometry["station"]["x"], 1.5)
        self.assertEqual(geometry["channels"][0]["connection"], [3, 4])

    def test_live_payload_merges_message_types(self) -> None:
        cache = {}
        result = _MAP.parse_location_payload(
            cache,
            "mower-1",
            [
                {
                    "type": 1,
                    "postureX": "4.5",
                    "postureY": 7,
                    "postureTheta": math.pi / 2,
                    "vehicleState": "isRunning",
                },
                {"type": 2, "mowingPercentage": 35},
                {"type": 3, "partitionIds": [9]},
            ],
        )
        self.assertEqual(result["x"], 4.5)
        self.assertAlmostEqual(result["heading"], 90.0)
        self.assertEqual(result["mowing_percentage"], 35)
        self.assertEqual(result["partition"], 9)
        progress = _MAP.parse_location_payload(
            cache, "mower-1", [{"type": 2, "mowingPercentage": 40}]
        )
        self.assertEqual(progress["x"], 4.5)
        self.assertFalse(progress["pose_updated"])

    def test_zone_for_point(self) -> None:
        zones = [
            {
                "id": 2,
                "name": "Back lawn",
                "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            }
        ]
        self.assertEqual(_MAP.zone_for_point(5, 5, zones)["id"], 2)
        self.assertIsNone(_MAP.zone_for_point(11, 5, zones))

    def test_map_identifier_fallback(self) -> None:
        resolved = _MAP.resolve_map_identifiers(
            {"map_id": 0, "map_base_id": 0},
            [{"mapId": 12, "mapBaseId": 13, "editTime": 99}],
        )
        self.assertEqual(resolved, ("12", "13", "99"))


if __name__ == "__main__":
    unittest.main()
