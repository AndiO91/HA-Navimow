"""Map geometry and live location helpers for Navimow Plus."""

from __future__ import annotations

import json
import math
from typing import Any


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _points_xy(points: Any) -> list[list[float]]:
    result: list[list[float]] = []
    if not isinstance(points, list):
        return result
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x, y = _as_float(point[0]), _as_float(point[1])
        if x is not None and y is not None:
            result.append([x, y])
    return result


def _boundary(points: Any) -> tuple[list[list[float]], list[int | None]]:
    polygon: list[list[float]] = []
    flags: list[int | None] = []
    if not isinstance(points, list):
        return polygon, flags
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x, y = _as_float(point[0]), _as_float(point[1])
        if x is None or y is None:
            continue
        polygon.append([x, y])
        flags.append(_as_int(point[2]) if len(point) >= 3 else None)
    return polygon, flags


def extract_map_geometry(raw: Any) -> dict[str, Any] | None:
    """Reduce a private-cloud map-detail response to card-safe geometry."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    detail = raw.get("map_detail", raw)
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except (TypeError, ValueError):
            return None
    if not isinstance(detail, dict) or not isinstance(detail.get("sub_maps"), list):
        return None

    zones: list[dict[str, Any]] = []
    station: dict[str, Any] | None = None
    for sub_map in detail.get("sub_maps") or []:
        if not isinstance(sub_map, dict):
            continue
        zone_id = _as_int(sub_map.get("id"))
        polygon: list[list[float]] = []
        flags: list[int | None] = []
        boundary_data: dict[str, Any] = {}
        for element in sub_map.get("elements") or []:
            if not isinstance(element, dict):
                continue
            element_type = element.get("type")
            if element_type == "BOUNDARY" and not polygon:
                polygon, flags = _boundary(element.get("points"))
                boundary_data = {
                    key: element.get(key)
                    for key in (
                        "boundary_type",
                        "mow_edge",
                        "obstacle_mow_edge",
                        "edge_vf",
                        "height_set",
                    )
                    if key in element
                }
            elif element_type == "CHARGING_PILE" and station is None:
                position = _points_xy([element.get("position")])
                if position:
                    station = {
                        "x": position[0][0],
                        "y": position[0][1],
                        "direction": _as_float(element.get("direction")),
                    }
        if zone_id is None and not polygon:
            continue
        zones.append(
            {
                "id": zone_id,
                "name": str(
                    sub_map.get("name")
                    or (f"Zone {zone_id}" if zone_id is not None else "Zone")
                ),
                "area": _as_float(sub_map.get("area")),
                "polygon": polygon,
                "boundary_flags": flags,
                "boundary": boundary_data,
            }
        )

    def polygons(key: str) -> list[list[list[float]]]:
        return [
            points
            for item in detail.get(key) or []
            if isinstance(item, dict) and (points := _points_xy(item.get("points")))
        ]

    channels: list[dict[str, Any]] = []
    for tunnel in detail.get("tunnels") or []:
        if not isinstance(tunnel, dict):
            continue
        points = _points_xy(tunnel.get("points"))
        if points:
            channels.append(
                {
                    "id": _as_int(tunnel.get("id")),
                    "name": str(tunnel.get("name") or ""),
                    "points": points,
                    "connection": [
                        parsed
                        for value in tunnel.get("connection") or []
                        if (parsed := _as_int(value)) is not None
                    ],
                }
            )

    return {
        "id": _as_int(detail.get("id")),
        "name": str(detail.get("name") or "Map"),
        "area": _as_float(detail.get("area")),
        "width": _as_float(detail.get("map_width")),
        "height": _as_float(detail.get("map_height")),
        "north_offset": _as_float(detail.get("map_north_offset")),
        "version": detail.get("version"),
        "modified_count": _as_int(detail.get("modifiedCount")),
        "zones": zones,
        "off_limit_areas": polygons("obstacles"),
        "vf_off_areas": polygons("vision_off_areas"),
        "channels": channels,
        "station": station,
    }


def valid_map_identifier(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "0"}


def resolve_map_identifiers(
    location: Any, map_list: Any
) -> tuple[str | None, str | None, str | None]:
    """Resolve map identifiers, falling back to map-list while docked."""
    candidates: list[dict[str, Any]] = []
    if isinstance(location, dict):
        candidates.append(location)
    if isinstance(map_list, list):
        candidates.extend(value for value in map_list if isinstance(value, dict))
    elif isinstance(map_list, dict):
        candidates.append(map_list)
        for key in ("list", "maps", "data"):
            values = map_list.get(key)
            if isinstance(values, list):
                candidates.extend(value for value in values if isinstance(value, dict))
    for candidate in candidates:
        map_id = candidate.get("map_id", candidate.get("mapId"))
        base_id = candidate.get("map_base_id", candidate.get("mapBaseId"))
        if not valid_map_identifier(map_id) or not valid_map_identifier(base_id):
            continue
        edit_time = candidate.get(
            "map_edit_time",
            candidate.get("edittime", candidate.get("editTime")),
        )
        return str(map_id), str(base_id), str(edit_time or "")
    return None, None, None


def location_topic(device_id: str) -> str:
    """Return the official MQTT topic containing dense mower pose updates."""
    return f"/downlink/vehicle/{device_id}/realtimeDate/location"


def parse_location_payload(
    cache: dict[str, dict[str, Any]], device_id: str, payload: Any
) -> dict[str, Any] | None:
    """Merge one observed location-array message into a device cache."""
    if not isinstance(payload, list):
        return None
    location = dict(cache.get(device_id) or {})
    location["device_id"] = device_id
    location["pose_updated"] = False
    changed = False
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == 1:
            x = _as_float(item.get("postureX"))
            y = _as_float(item.get("postureY"))
            theta = _as_float(item.get("postureTheta"))
            if x is not None and y is not None and theta is not None:
                location.update(
                    {
                        "x": x,
                        "y": y,
                        "theta": theta,
                        "heading": math.degrees(theta) % 360,
                        "pose_updated": True,
                    }
                )
                changed = True
            if "vehicleState" in item:
                location["vehicle_state"] = item.get("vehicleState")
            if "time" in item:
                location["pose_time"] = item.get("time")
        elif item_type == 2:
            for source, target in (
                ("currentMowBoundary", "mow_boundary"),
                ("currentMowProgress", "mow_progress"),
                ("mowingPercentage", "mowing_percentage"),
                ("subtotalArea", "subtotal_area"),
            ):
                if source in item:
                    location[target] = item.get(source)
                    changed = True
        elif item_type == 3 and "partitionIds" in item:
            partitions = item.get("partitionIds")
            location["partition_ids"] = partitions
            location["partition"] = (
                partitions[0] if isinstance(partitions, list) and partitions else None
            )
            changed = True
        elif item_type == 4:
            location["task_delay"] = item.get("taskDelay")
            changed = True
    if not changed:
        return None
    cache[device_id] = location
    return location


def zone_for_point(
    x: float | None, y: float | None, zones: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Return the map zone containing an X/Y position."""
    if x is None or y is None:
        return None
    for zone in zones:
        polygon = zone.get("polygon")
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        inside = False
        previous = polygon[-1]
        for current in polygon:
            x1, y1 = float(previous[0]), float(previous[1])
            x2, y2 = float(current[0]), float(current[1])
            if (y1 > y) != (y2 > y):
                crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < crossing:
                    inside = not inside
            previous = current
        if inside:
            return zone
    return None
