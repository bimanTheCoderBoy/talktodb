"""Default parameters and UI schemas for customizable built-in audit rules."""
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set


def _lte_su_mimo_defaults():
    return {
        "columns": [
            {"key": "lte_sumimosupportdl", "label": "SU-MIMO DL", "enabled": True, "require_true": True},
            {"key": "lte_sumimosupportul", "label": "SU-MIMO UL", "enabled": True, "require_true": True},
        ]
    }


def _lte_mu_mimo_defaults():
    return {
        "boolean_columns": [
            {"key": "lte_mumimosupportdl", "label": "MU-MIMO DL", "enabled": True, "require_true": True},
            {"key": "lte_mumimosupportul", "label": "MU-MIMO UL", "enabled": True, "require_true": True},
        ],
        "numeric_columns": [
            {"key": "lte_mumimotermsdl", "label": "MU-MIMO Terms DL", "enabled": True, "require_value": True, "min": None, "max": None},
            {"key": "lte_mumimotermsul", "label": "MU-MIMO Terms UL", "enabled": True, "require_value": True, "min": None, "max": None},
        ],
    }


def _lte_beamforming_defaults():
    return {
        "columns": [
            {"key": "lte_beamformingsupportdl", "label": "Beamforming DL", "enabled": True, "require_true": True},
            {"key": "lte_beamformingsupportul", "label": "Beamforming UL", "enabled": True, "require_true": True},
        ]
    }


def _lte_rx_tx_defaults():
    return {
        "columns": [
            {"key": "lte_sumimotxelems", "label": "TX Elements", "enabled": True, "require_value": True, "min": None, "max": None},
            {"key": "lte_sumimorxelems", "label": "RX Elements", "enabled": True, "require_value": True, "min": None, "max": None},
        ]
    }


def _lte_signal_thresholds_defaults():
    return {
        "columns": [
            {"key": "lte_carrierparameters_rsrpthreshold", "label": "RSRP Threshold", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "lte_carrierparameters_sinrthreshold", "label": "SINR Threshold", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    }


def _lte_coverage_range_defaults():
    return {
        "columns": [
            {"key": "lte_carrierparameters_maxrange", "label": "Max Range", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "lte_preamblecellrange_ro", "label": "Preamble Cell Range", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    }


def _lte_interference_defaults():
    return {
        "columns": [
            {
                "key": "lte_carrierparameters_intertechinterference_nrnoiserisecellterm",
                "label": "Inter-tech Interference",
                "enabled": True,
                "require_value": False,
                "min": None,
                "max": None,
            }
        ]
    }


def _lte_cell_load_defaults():
    return {
        "columns": [
            {"key": "lte_carrierparameters_cellload_avgnumofconnusers", "label": "Avg Connected Users", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "lte_carrierparameters_cellload_cellcentredl", "label": "Cell Centre DL", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "lte_carrierparameters_cellload_celledgedl", "label": "Cell Edge DL", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    }


def _lte_coverage_height_defaults():
    return {
        "columns": [
            {"key": "coverage_km", "label": "Coverage (km)", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "antenna_height_m", "label": "Antenna Height (m)", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    }


def _lte_orientation_defaults():
    return {
        "columns": [
            {"key": "azimuth", "label": "Azimuth", "enabled": True, "require_value": False, "min": 0, "max": 360},
            {"key": "tilt", "label": "Tilt", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    }


def _lte_high_level_metrics():
    return {
        "metrics": {
            "eci_assigned": True,
            "ecgi_assigned": True,
            "tac_assigned": True,
            "carrier_assigned": True,
            "rsi_assigned": True,
            "tx_power_configured": True,
            "rs_power_configured": True,
            "bandwidth_configured": True,
            "carrier_earfcn_configured": True,
            "carrier_aggregation_enabled": True,
            "su_mimo_enabled": True,
            "mu_mimo_enabled": True,
            "beamforming_enabled": True,
            "coverage_range_configured": True,
            "cell_load_configured": True,
            "downtilt_compliant": True,
        }
    }


def _nr_su_mimo_defaults():
    return {
        "columns": [
            {"key": "nrt_sumimosupportdl", "label": "SU-MIMO DL", "enabled": True, "require_true": True},
            {"key": "nrt_sumimosupportul", "label": "SU-MIMO UL", "enabled": True, "require_true": True},
        ]
    }


def _nr_mu_mimo_defaults():
    return {
        "boolean_columns": [
            {"key": "nrt_mumimosupportdl", "label": "MU-MIMO DL", "enabled": True, "require_true": True},
            {"key": "nrt_mumimosupportul", "label": "MU-MIMO UL", "enabled": True, "require_true": True},
        ],
        "numeric_columns": [
            {"key": "nrt_mumimotermsdl", "label": "MU-MIMO Terms DL", "enabled": True, "require_value": True, "min": None, "max": None},
            {"key": "nrt_mumimotermsul", "label": "MU-MIMO Terms UL", "enabled": True, "require_value": True, "min": None, "max": None},
        ],
    }


def _nr_beamforming_defaults():
    return {
        "columns": [
            {"key": "nrt_beamformingsupportdl", "label": "Beamforming DL", "enabled": True, "require_true": True},
            {"key": "nrt_beamformingsupportul", "label": "Beamforming UL", "enabled": True, "require_true": True},
        ]
    }


def _site_high_level_metrics():
    return {
        "metrics": {
            "beamforming_supported": True,
            "sites_with_antennas": True,
            "sites_with_lte_tac": True,
            "sites_with_nr_tac": True,
            "total_cells": True,
            "lte_cells": True,
            "nr_cells": True,
        }
    }


BUILTIN_RULE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "carrier_assignment_lte": {"pci_min": 0, "pci_max": 503, "pci_column": "pci"},
    "carrier_assignment_nr": {"pci_min": 0, "pci_max": 1007, "pci_column": "pci"},
    "carrier_aggregation_lte": {"expected_value": True, "column": "lte_carrierparameters_caenabledatcell"},
    "carrier_aggregation_nr": {"expected_value": True, "column": "nrt_carrierparameters_caenabledatcell"},
    "su_mimo_lte": _lte_su_mimo_defaults(),
    "su_mimo_nr": _nr_su_mimo_defaults(),
    "mu_mimo_lte": _lte_mu_mimo_defaults(),
    "mu_mimo_nr": _nr_mu_mimo_defaults(),
    "rx_tx_elements_lte": _lte_rx_tx_defaults(),
    "rx_tx_elements_nr": {
        "columns": [
            {"key": "nrt_sumimotxelems", "label": "TX Elements", "enabled": True, "require_value": True, "min": None, "max": None},
            {"key": "nrt_sumimorxelems", "label": "RX Elements", "enabled": True, "require_value": True, "min": None, "max": None},
        ]
    },
    "beamforming_support_lte": _lte_beamforming_defaults(),
    "beamforming_support_nr": _nr_beamforming_defaults(),
    "signal_thresholds_lte": _lte_signal_thresholds_defaults(),
    "signal_thresholds_nr": {
        "columns": [
            {"key": "nrt_carrierparameters_ssrsrpthreshold", "label": "SS-RSRP Threshold", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "nrt_carrierparameters_sinrthreshold", "label": "SINR Threshold", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "nrt_carrierparameters_csirsrpthreshold", "label": "CSI-RSRP Threshold", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    },
    "coverage_range_lte": _lte_coverage_range_defaults(),
    "coverage_range_nr": {
        "columns": [
            {"key": "nrt_carrierparameters_maxrange", "label": "Max Range", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "coverage_range", "label": "CS Range", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    },
    "interference_lte": _lte_interference_defaults(),
    "interference_nr": {
        "columns": [
            {"key": "nrt_carrierparameters_intertechinterference_ltenoiserisecellter", "label": "Inter-tech LTE Noise UL", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "nrt_carrierparameters_noiserisecelltermtotalul_ro", "label": "Noise Rise Cell Term UL", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    },
    "cell_load_lte": _lte_cell_load_defaults(),
    "cell_load_nr": {
        "columns": [
            {"key": "nrt_carrierparameters_cellbandwidthparts_avgnumofconnusers", "label": "Avg Connected Users", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "nrt_carrierparameters_cellbandwidthparts_cellloadpcntdl", "label": "Cell Load DL %", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "nrt_carrierparameters_cellbandwidthparts_cellloadpcntul", "label": "Cell Load UL %", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    },
    "coverage_and_height_lte": _lte_coverage_height_defaults(),
    "coverage_and_height_nr": {
        "columns": [
            {"key": "coverage_km", "label": "Coverage (km)", "enabled": True, "require_value": False, "min": None, "max": None},
            {"key": "antenna_height_m", "label": "Antenna Height (m)", "enabled": True, "require_value": False, "min": None, "max": None},
        ]
    },
    "antenna_orientation_lte": _lte_orientation_defaults(),
    "antenna_orientation_nr": _lte_orientation_defaults(),
    "downtilt_compliance_lte": {"use_db_constraints": True, "fixed_min": 0, "fixed_max": 90},
    "downtilt_compliance_nr": {"use_db_constraints": True, "fixed_min": 0, "fixed_max": 90},
    "cell_identity_lte": {"pci_min": 0, "pci_max": 503, "require_eci": True, "require_ecgi": True, "require_tac": True, "require_pci": True},
    "cell_identity_nr": {"pci_min": 0, "pci_max": 1007, "require_tac": True, "require_pci": True},
    "rach_rsi_lte": {"rsi_min": 0, "rsi_max": 837},
    "rach_rsi_nr": {"rsi_min": 0, "rsi_max": 837, "require_rsi": True},
    "rf_power_lte": {"tx_min_dbm": 10, "tx_max_dbm": 60, "require_rs_power": True},
    "rf_power_nr": {"tx_min_dbm": 10, "tx_max_dbm": 70, "require_rs_power": False},
    "cell_high_level_stats_lte": _lte_high_level_metrics(),
    "cell_high_level_stats_nr": {
        "metrics": {
            "tac_assigned": True,
            "carrier_assigned": True,
            "rsi_assigned": True,
            "tx_power_configured": True,
            "dl_arfcn_configured": True,
            "dl_prbs_configured": True,
            "carrier_aggregation_enabled": True,
            "su_mimo_enabled": True,
            "mu_mimo_enabled": True,
            "beamforming_enabled": True,
            "coverage_range_configured": True,
            "cell_load_configured": True,
            "downtilt_compliant": True,
        }
    },
    "beamforming_support": {"expected_outcome": "Yes", "min_cells_with_beamforming": 1},
    "site_high_level_stats": _site_high_level_metrics(),
}

CUSTOMIZABLE_BUILTIN_RULE_KEYS: Set[str] = set(BUILTIN_RULE_DEFAULTS.keys())


def merge_rule_config(rule_key: str, user_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Deep-merge user overrides onto built-in defaults."""
    defaults = deepcopy(BUILTIN_RULE_DEFAULTS.get(rule_key, {}))
    if not user_overrides:
        return defaults
    return _deep_merge(defaults, user_overrides)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = value
        else:
            result[key] = value
    return result


def get_customizable_rule_schema(rule_key: str) -> Optional[Dict[str, Any]]:
    """Return UI schema metadata for a customizable rule."""
    if rule_key not in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
        return None
    defaults = BUILTIN_RULE_DEFAULTS[rule_key]
    return {"rule_key": rule_key, "defaults": defaults, "fields": _fields_for_rule(rule_key, defaults)}


def _fields_for_rule(rule_key: str, defaults: Dict[str, Any]) -> List[Dict[str, Any]]:
    if rule_key.startswith("carrier_assignment"):
        return [
            {"key": "pci_min", "type": "number", "label": "PCI Min"},
            {"key": "pci_max", "type": "number", "label": "PCI Max"},
        ]
    if rule_key.startswith("carrier_aggregation"):
        return [{"key": "expected_value", "type": "select", "label": "Expected CA Value", "options": ["True", "False"]}]
    if rule_key.startswith("su_mimo") or rule_key.startswith("beamforming_support_"):
        return [{"key": "columns", "type": "boolean_columns", "label": "Boolean Columns"}]
    if rule_key.startswith("mu_mimo"):
        return [
            {"key": "boolean_columns", "type": "boolean_columns", "label": "Boolean Columns (require true)"},
            {"key": "numeric_columns", "type": "numeric_columns", "label": "Numeric Columns (require value / range)"},
        ]
    if rule_key.startswith(("rx_tx_elements", "signal_thresholds", "coverage_range", "interference", "cell_load", "coverage_and_height", "antenna_orientation")) or rule_key.startswith("coverage_and_height"):
        return [{"key": "columns", "type": "numeric_columns", "label": "Column Checks"}]
    if rule_key.startswith("downtilt_compliance"):
        return [
            {"key": "use_db_constraints", "type": "boolean", "label": "Use DB Constraint Min/Max"},
            {"key": "fixed_min", "type": "number", "label": "Fixed Min Tilt (when not using DB)"},
            {"key": "fixed_max", "type": "number", "label": "Fixed Max Tilt (when not using DB)"},
        ]
    if rule_key.startswith("cell_identity"):
        fields = [
            {"key": "pci_min", "type": "number", "label": "PCI Min"},
            {"key": "pci_max", "type": "number", "label": "PCI Max"},
            {"key": "require_tac", "type": "boolean", "label": "Require TAC"},
            {"key": "require_pci", "type": "boolean", "label": "Require PCI"},
        ]
        if "lte" in rule_key:
            fields.extend([
                {"key": "require_eci", "type": "boolean", "label": "Require ECI"},
                {"key": "require_ecgi", "type": "boolean", "label": "Require ECGI"},
            ])
        return fields
    if rule_key.startswith("rach_rsi"):
        fields = [
            {"key": "rsi_min", "type": "number", "label": "RSI Min"},
            {"key": "rsi_max", "type": "number", "label": "RSI Max"},
            {"key": "require_rsi", "type": "boolean", "label": "Require RSI"},
        ]
        return fields
    if rule_key.startswith("rf_power"):
        return [
            {"key": "tx_min_dbm", "type": "number", "label": "Tx Power Min (dBm)"},
            {"key": "tx_max_dbm", "type": "number", "label": "Tx Power Max (dBm)"},
            {"key": "require_rs_power", "type": "boolean", "label": "Require RS Power"},
        ]
    if rule_key.startswith("cell_high_level_stats") or rule_key == "site_high_level_stats":
        return [{"key": "metrics", "type": "metric_toggles", "label": "Metrics to Show"}]
    if rule_key == "beamforming_support":
        return [
            {"key": "expected_outcome", "type": "select", "label": "Expected Outcome", "options": ["Yes", "No"]},
            {"key": "min_cells_with_beamforming", "type": "number", "label": "Min Cells With Beamforming"},
        ]
    return []
