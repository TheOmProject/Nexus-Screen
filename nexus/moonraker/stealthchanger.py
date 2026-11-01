"""StealthChanger capability detection (klipper-toolchanger `toolchanger` + `tool <name>` objects)."""


def detect(objects):
    return "toolchanger" in objects


def query_objects(objects):
    if not detect(objects):
        return []
    return ["toolchanger"] + sorted(o for o in objects if o.startswith("tool "))


def parse(status, meta=None):
    """Return {"tools", "active", "status", "details": [...]} or None.

    `meta` holds per-tool colour/material kept by Nexus Screen in Moonraker's
    database (klipper-toolchanger itself has no such fields).
    """
    tc = status.get("toolchanger")
    if not tc:
        return None
    meta = meta or {}
    names = list(tc.get("tool_names") or [])
    numbers = list(tc.get("tool_numbers") or [])
    if not names and numbers:
        names = [f"T{n}" for n in numbers]
    if not names:
        return None
    active = None
    current = tc.get("tool_number")
    if current is not None and current in numbers:
        active = numbers.index(current)
    elif tc.get("tool") in names:
        active = names.index(tc["tool"])
    details = []
    for i, name in enumerate(names):
        obj = status.get(f"tool {name}", {})
        m = meta.get(name, {})
        details.append({
            "name": name,
            "number": numbers[i] if i < len(numbers) else obj.get("tool_number", i),
            "extruder": obj.get("extruder") or ("extruder" if i == 0 else f"extruder{i}"),
            "state": "Active" if i == active else "Docked",
            "color": m.get("color", "#8A8D91"),
            "material": m.get("material", "--"),
        })
    return {"tools": names, "active": active, "status": tc.get("status", ""), "details": details}
