"""Fans, lights and toolhead status from Klipper objects (discovered, never assumed)."""

_FAN_KINDS = (("heater_fan ", "auto"), ("controller_fan ", "auto"), ("temperature_fan ", "auto"),
              ("fan_generic ", "generic"))
_LED_PREFIXES = ("neopixel ", "dotstar ", "led ", "pca9533 ", "pca9632 ")


def heater_name(obj):
    """Klipper heater name for SET_HEATER_TEMPERATURE ('heater_generic chamber' -> 'chamber')."""
    return obj.split(" ", 1)[1] if obj.startswith("heater_generic ") else obj


def fan_objects(objects):
    return sorted(o for o in objects if o == "fan" or o.startswith(tuple(p for p, _ in _FAN_KINDS)))


def light_objects(objects):
    return sorted(o for o in objects if o.startswith(_LED_PREFIXES))


def _title(name):
    return name.replace("_", " ").title()


def parse_fans(status):
    """[{id, name, sub, kind: part|generic|auto, param, speed 0..1}] — 'auto' fans are
    driven by Klipper (heater/controller/temperature fans) and are display-only."""
    fans = []
    for obj in sorted(status):
        if obj == "fan":
            kind, short, name = "part", "fan", "Part Cooling Fan"
        else:
            match = next(((p, k) for p, k in _FAN_KINDS if obj.startswith(p)), None)
            if not match:
                continue
            kind, short = match[1], obj[len(match[0]):]
            name = _title(short)
        fans.append({"id": obj, "name": name, "sub": obj + (" (M106)" if kind == "part" else ""),
                     "kind": kind, "param": short, "speed": float(status[obj].get("speed") or 0.0)})
    order = {"part": 0, "auto": 1, "generic": 2}
    return sorted(fans, key=lambda f: (order[f["kind"]], f["id"]))


def parse_lights(status):
    """[{id, name, led, color: (r, g, b)}] using the first chip of each LED chain."""
    lights = []
    for obj in sorted(status):
        if not obj.startswith(_LED_PREFIXES):
            continue
        data = status[obj].get("color_data") or [[0, 0, 0, 0]]
        r, g, b = (list(data[0]) + [0, 0, 0])[:3]
        led = obj.split(" ", 1)[1]
        lights.append({"id": obj, "name": _title(led), "led": led, "color": (float(r), float(g), float(b))})
    return lights


def parse_toolhead(status):
    th = status.get("toolhead") or {}
    return {"homed": th.get("homed_axes", ""),
            "min": list(th.get("axis_minimum") or [0, 0, 0])[:3],
            "max": list(th.get("axis_maximum") or [0, 0, 0])[:3],
            "pos": list((status.get("gcode_move") or {}).get("gcode_position") or th.get("position") or [0, 0, 0])[:3],
            "limits": {k: th.get(k) for k in ("max_velocity", "max_accel", "square_corner_velocity")}}


def parse_mesh(bm):
    """bed_mesh status -> {active, matrix, profiles: {name: points}, min, max}. `matrix` is the
    loaded (probed) mesh, or None when no mesh is active."""
    if bm is None:
        return None
    probed = bm.get("probed_matrix") or []
    active = bm.get("profile_name") or ""
    return {"active": active,
            "matrix": probed if probed and probed[0] else None,
            "profiles": {name: p.get("points") for name, p in (bm.get("profiles") or {}).items() if p.get("points")},
            "min": list(bm.get("mesh_min") or [0, 0]), "max": list(bm.get("mesh_max") or [0, 0])}


def screw_names(settings):
    """Screw labels from [screws_tilt_adjust] (screwN / screwN_name), or None if not configured."""
    cfg = settings.get("screws_tilt_adjust")
    if cfg is None:
        return None
    names, i = [], 1
    while f"screw{i}" in cfg:
        names.append(cfg.get(f"screw{i}_name") or f"Screw {i}")
        i += 1
    return names


def parse_screws(names, status):
    """[{name, dz (mm vs base), adjust ('CW 00:15'), base}] from screws_tilt_adjust results."""
    if names is None:
        return None
    results = (status.get("screws_tilt_adjust") or {}).get("results") or {}
    base_z = next((r.get("z") for r in results.values() if r.get("is_base")), None)
    out = []
    for i, name in enumerate(names, 1):
        r = results.get(f"screw{i}")
        out.append({"name": name,
                    "dz": None if r is None or base_z is None else r.get("z", 0.0) - base_z,
                    "adjust": None if r is None else f"{r.get('sign', '')} {r.get('adjust', '')}".strip(),
                    "base": bool(r and r.get("is_base"))})
    return {"screws": out, "measured": bool(results),
            "error": bool((status.get("screws_tilt_adjust") or {}).get("error"))}


def parse_macros(settings):
    """Visible macros (names not starting with '_'): {NAME: {description, gcode}}."""
    out = {}
    for key, cfg in settings.items():
        if key.startswith("gcode_macro "):
            name = key.split(" ", 1)[1].upper()
            if not name.startswith("_"):
                out[name] = {"description": cfg.get("description") or "", "gcode": (cfg.get("gcode") or "").strip()}
    return dict(sorted(out.items()))


def config_summary(settings):
    """The few config values screens display (input shaper, kinematics, homing positions)."""
    shaper = settings.get("input_shaper") or {}
    printer = settings.get("printer") or {}
    return {"shaper": {"type_x": shaper.get("shaper_type_x") or shaper.get("shaper_type"),
                       "type_y": shaper.get("shaper_type_y") or shaper.get("shaper_type"),
                       "freq_x": shaper.get("shaper_freq_x"), "freq_y": shaper.get("shaper_freq_y")} if shaper else None,
            "kinematics": printer.get("kinematics"),
            "homing": {a: (settings.get(f"stepper_{a}") or {}).get("position_endstop") for a in "xyz"}}
