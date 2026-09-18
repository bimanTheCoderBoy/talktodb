"""Technology-specific config path resolver.

All tech-dependent JSON configs (base templates, column specs, GDL
mappings, EDS payload mappings) live under::

    config/json_config/{lte|nr}/

This module provides ``TechConfig`` which resolves the correct file path
for a given technology string (``"LTE"`` or ``"NR"``).

Usage::

    from config.tech_config_resolver import TechConfig
    cfg = TechConfig("LTE")
    cfg.columns_path              # config/json_config/lte/columns.json
    cfg.cell_eds_mapping_path     # config/json_config/lte/cell_eds_mapping.json
"""

import os
from pathlib import Path
from functools import lru_cache

_CONFIG_DIR = str(Path(__file__).resolve().parent / "json_config")


class TechConfig:
    """Resolve technology-specific config file paths."""

    def __init__(self, tech: str):
        self._tech = tech.upper()
        if self._tech not in ("LTE", "NR"):
            raise ValueError(f"Unsupported technology: {tech!r}. Must be 'LTE' or 'NR'.")
        self._tech_dir = os.path.join(_CONFIG_DIR, self._tech.lower())

    @property
    def technology(self) -> str:
        return self._tech

    def _path(self, filename: str) -> str:
        return os.path.join(self._tech_dir, filename)

    @property
    def columns_path(self) -> str:
        return self._path("columns.json")

    @property
    def mu_base_path(self) -> str:
        return self._path("mu_base.json")

    @property
    def cell_base_path(self) -> str:
        return self._path("cell_base.json")

    @property
    def mu_eds_mapping_path(self) -> str:
        return self._path("mu_eds_mapping.json")

    @property
    def cell_eds_mapping_path(self) -> str:
        return self._path("cell_eds_mapping.json")

    @property
    def location_eds_mapping_path(self) -> str:
        return self._path("location_eds_mapping.json")

    @property
    def location_base_path(self) -> str:
        return self._path("location_base.json")

    @property
    def gdl_defaults_path(self) -> str:
        return self._path("gdl_defaults.json")


@lru_cache(maxsize=4)
def get_tech_config(tech: str) -> TechConfig:
    """Cached factory for TechConfig instances."""
    return TechConfig(tech)
