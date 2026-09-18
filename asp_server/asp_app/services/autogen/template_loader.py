"""
Loader for the static antenna template catalog at
config/json_config/antenna_templates.json (created in plan 02-01).

The catalog is loaded once per process, cached in a module-level dict.
The synthesizer (plan 02-05) calls get_template(name) for every candidate;
the auto-gen API endpoint (plan 02-06) calls list_template_names() to
populate the dropdown.

Tilt resolution: tilt_range here is a coarse continuous-clamp guard
(used when no operator-uploaded tilt mapping is available). The
canonical source of valid tilts is the CSV the engineer uploads via
``POST /setup/tilt-mapping`` — see services.autogen.tilt_mapping.

v2 enhancement (deferred): replace this with a live ASSET catalog query
exposed via a new GET /asset/antenna-devices endpoint.
"""
import json
import os
from functools import lru_cache
from typing import Dict, List

from asp_app.config.acss_config import get_antenna_template_catalog_path


@lru_cache(maxsize=1)
def load_antenna_templates() -> Dict:
    """Returns the parsed JSON catalog. Cached for process lifetime."""
    path = get_antenna_template_catalog_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Antenna template catalog not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_template_names() -> List[str]:
    """All known template names. Default first, then alphabetical for the rest."""
    catalog = load_antenna_templates()
    default = catalog.get("default")
    all_names = list(catalog.get("templates", {}).keys())
    if default and default in all_names:
        rest = sorted(n for n in all_names if n != default)
        return [default] + rest
    return sorted(all_names)


def get_template(name: str) -> Dict:
    """Returns the gdl_defaults dict for a named template.

    Raises KeyError if the template is unknown.
    """
    catalog = load_antenna_templates()
    templates = catalog.get("templates", {})
    if name not in templates:
        raise KeyError(f"Unknown antenna template: {name!r}")
    return templates[name].get("gdl_defaults", {})


def get_default_template_name() -> str:
    """Returns the catalog's declared default name."""
    return load_antenna_templates().get("default", "")


def get_template_meta(name: str) -> Dict:
    """Returns the *full* template entry including non-gdl_defaults metadata
    (tilt_range, description, etc.). Raises KeyError if unknown.
    """
    catalog = load_antenna_templates()
    templates = catalog.get("templates", {})
    if name not in templates:
        raise KeyError(f"Unknown antenna template: {name!r}")
    return templates[name]


def get_tilt_range(name: str) -> Dict:
    """Returns ``{'min': float, 'max': float}`` for the named template's
    electrical tilt. Falls back to a generic 0..12° range if the template
    does not declare one (older catalog entries pre-dating the tilt_range
    field will continue to work without error).
    """
    meta = get_template_meta(name)
    tr = meta.get("tilt_range") or {}
    return {
        "min": float(tr.get("min", 0.0)),
        "max": float(tr.get("max", 12.0)),
    }


def get_default_tilt(name: str) -> float:
    """Returns the template's baked-in Electrical Tilt default. Falls back
    to the midpoint of the tilt_range if the GDL default key is missing.
    """
    defaults = get_template(name)
    val = defaults.get("Property: Logical Antenna: Electrical Tilt (deg)")
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    tr = get_tilt_range(name)
    return (tr["min"] + tr["max"]) / 2.0
