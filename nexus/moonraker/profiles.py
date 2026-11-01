"""Filament profiles. Stored by Nexus Screen in Moonraker's database
(namespace nexus_screen, key filament_profiles) — never in printer configuration.
Profile values are reference data for the UI; only the temperatures are used to heat."""
import copy

FIELDS = [  # key, label, unit, lo, hi, int digits, decimals
    ("nozzle", "Nozzle Temperature", "°C", 0, 350, 3, 0),
    ("bed", "Bed Temperature", "°C", 0, 150, 3, 0),
    ("speed", "Print Speed", "mm/s", 1, 999, 3, 0),
    ("fan", "Fan Speed", "%", 0, 100, 3, 0),
    ("flow", "Flow Rate", "%", 50, 150, 3, 0),
]

# PLA/PETG/ABS/TPU temperatures match the approved Temperature presets; ASA/PC nozzle values
# match the add-on material defaults. Bed values for ASA/PC and speed/fan/flow are editable
# placeholders.
_DEFAULTS = [("PLA", 220, 60), ("PETG", 230, 70), ("ABS", 240, 100), ("TPU", 210, 50),
             ("ASA", 255, 100), ("PC", 270, 110)]
DEFAULT_STORE = {"active": "PLA",
                 "profiles": [{"name": n, "nozzle": nz, "bed": bd, "speed": 100, "fan": 100, "flow": 100}
                              for n, nz, bd in _DEFAULTS]}


def defaults():
    return copy.deepcopy(DEFAULT_STORE)


def find(store, name):
    return next((p for p in store["profiles"] if p["name"] == name), None)


def unique_name(store, base):
    names = {p["name"] for p in store["profiles"]}
    i = 1
    while f"{base} {i}" in names:
        i += 1
    return f"{base} {i}"


def add(store, template=None):
    s = copy.deepcopy(store)
    src = template or find(s, s["active"]) or s["profiles"][0]
    new = dict(src, name=unique_name(s, "Custom" if template is None else src["name"]))
    s["profiles"].append(new)
    return s, new["name"]


def delete(store, name):
    s = copy.deepcopy(store)
    if len(s["profiles"]) <= 1:
        return s
    s["profiles"] = [p for p in s["profiles"] if p["name"] != name]
    if s["active"] == name:
        s["active"] = s["profiles"][0]["name"]
    return s


def update(store, name, **values):
    s = copy.deepcopy(store)
    p = find(s, name)
    if p:
        p.update(values)
    return s
