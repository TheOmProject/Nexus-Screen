"""BoxTurtle capability detection (AFC-Klipper-Add-On objects)."""

_LANE_PREFIXES = ("AFC_stepper ", "AFC_lane ")


def detect(objects):
    return "AFC" in objects


def lane_objects(objects):
    return [o for o in objects if o.startswith(_LANE_PREFIXES)]


def query_objects(objects):
    return (["AFC"] + lane_objects(objects)) if detect(objects) else []


def _colour(value):
    if not value:
        return "#5d636b"
    value = str(value).strip()
    return value if value.startswith("#") else f"#{value}"


def parse(status):
    """Return {"lanes": [...], "current", "state", "error"} or None."""
    afc = status.get("AFC")
    if afc is None:
        return None
    lane_status = {}
    for key, val in status.items():
        for prefix in _LANE_PREFIXES:
            if key.startswith(prefix):
                lane_status[key[len(prefix):]] = val or {}
    order = list(afc.get("lanes") or sorted(lane_status))
    current = afc.get("current_load") or afc.get("current_lane")
    lanes = []
    for i, name in enumerate(order):
        st = lane_status.get(name, {})
        lanes.append({
            "name": str(i + 1),
            "id": name,
            "color": _colour(st.get("color")),
            "loaded": bool(st.get("prep") or st.get("load") or st.get("tool_loaded")),
            "sensor": bool(st.get("prep")),
            "tool_loaded": bool(st.get("tool_loaded")) or name == current,
            "material": st.get("material") or "",
            "temp": st.get("extruder_temp"),
            "runout": st.get("runout_lane"),
            "buffer": st.get("buffer_status"),
        })
    if not lanes:
        return None
    error = afc.get("error_state")
    return {"lanes": lanes, "current": current, "error": bool(error),
            "state": afc.get("current_state") or ("Error" if error else "Ready")}
