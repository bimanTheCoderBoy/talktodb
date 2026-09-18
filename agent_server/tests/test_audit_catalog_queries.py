"""Tests for multi-table custom rule query building."""
import pytest

from db_agent_v2.tools.audit_engine.catalog import (
    build_multi_table_fetch_query,
    column_result_key,
    resolve_anchor_table,
    validate_custom_rule_payload,
    validate_rule_type_for_column,
)


def _checks(*items):
    return [
        {
            "table_name": table,
            "column": column,
            "rule_type": "not_null",
            "rule_params": {},
        }
        for table, column in items
    ]


class TestResolveAnchor:
    def test_cell_lte_anchor(self):
        assert resolve_anchor_table("cell", {"cell_lte", "cell_physical_antenna"}) == "cell_lte"

    def test_site_always_location(self):
        assert resolve_anchor_table("site", {"cell_lte"}) == "location"

    def test_rejects_lte_nr_mix(self):
        with pytest.raises(ValueError, match="Cannot mix LTE and NR"):
            resolve_anchor_table("cell", {"cell_lte", "cell_nr"})

    def test_cell_location_requires_cell_table(self):
        with pytest.raises(ValueError, match="require an LTE or NR"):
            resolve_anchor_table("cell", {"location"})


class TestBuildQuery:
    def test_single_table_cell_lte(self):
        query = build_multi_table_fetch_query(
            "cell",
            _checks(("cell_lte", "lte_tac")),
        )
        assert "FROM cell_lte c_lte" in query
        assert 'c_lte.lte_tac AS "cell_lte.lte_tac"' in query
        assert "c_lte.iid = ANY($1::text[])" in query

    def test_cell_lte_join_physical_antenna(self):
        query = build_multi_table_fetch_query(
            "cell",
            _checks(
                ("cell_lte", "lte_tac"),
                ("cell_physical_antenna", "tilt"),
            ),
        )
        assert "FROM cell_lte c_lte" in query
        assert "LEFT JOIN cell_physical_antenna cpa ON c_lte.cell_iid = cpa.cell_iid" in query
        assert 'cpa.tilt AS "cell_physical_antenna.tilt"' in query

    def test_cell_lte_join_logical_and_location(self):
        query = build_multi_table_fetch_query(
            "cell",
            _checks(
                ("cell_lte", "lte_tac"),
                ("cell_logical_antenna", "primarymodel_radiuskm"),
                ("location", "town"),
            ),
        )
        assert "LEFT JOIN cell_logical_antenna cla ON c_lte.cell_iid = cla.cell_iid" in query
        assert "LEFT JOIN location loc ON c_lte.location_iid = loc.iid" in query

    def test_site_location_join_lte_and_antennas(self):
        query = build_multi_table_fetch_query(
            "site",
            _checks(
                ("location", "town"),
                ("cell_lte", "lte_tac"),
                ("cell_physical_antenna", "azimuth"),
                ("cell_logical_antenna", "correctionfactor"),
            ),
        )
        assert "FROM location loc" in query
        assert "LEFT JOIN cell_lte c_lte ON loc.eid = c_lte.location_eid" in query
        assert "LEFT JOIN cell_physical_antenna cpa ON loc.eid = cpa.location_eid" in query
        assert "LEFT JOIN cell_logical_antenna cla ON loc.eid = cla.location_eid" in query
        assert "loc.iid = ANY($1::text[])" in query

    def test_antenna_only_cell_audit(self):
        query = build_multi_table_fetch_query(
            "cell",
            _checks(("cell_physical_antenna", "tilt")),
        )
        assert "FROM cell_physical_antenna cpa" in query
        assert "cpa.cell_iid = ANY($1::text[])" in query

    def test_physical_to_logical_antenna_path(self):
        query = build_multi_table_fetch_query(
            "cell",
            _checks(
                ("cell_physical_antenna", "tilt"),
                ("cell_logical_antenna", "correctionfactor"),
            ),
        )
        assert "LEFT JOIN cell_logical_antenna cla ON cpa.cell_iid = cla.cell_iid" in query


class TestValidation:
    def test_valid_multi_table_payload(self):
        validate_custom_rule_payload(
            "cell",
            _checks(
                ("cell_lte", "lte_tac"),
                ("cell_physical_antenna", "tilt"),
            ),
        )

    def test_cell_audit_with_site_table(self):
        validate_custom_rule_payload(
            "cell",
            _checks(
                ("cell_lte", "lte_tac"),
                ("location", "town"),
            ),
        )

    def test_site_audit_with_cell_table(self):
        validate_custom_rule_payload(
            "site",
            _checks(
                ("location", "town"),
                ("cell_lte", "lte_tac"),
            ),
        )

    def test_duplicate_table_column_pair_rejected(self):
        with pytest.raises(ValueError, match="Duplicate"):
            validate_custom_rule_payload(
                "cell",
                _checks(
                    ("cell_lte", "lte_tac"),
                    ("cell_lte", "lte_tac"),
                ),
            )

    def test_float_column_rejects_boolean_check(self):
        with pytest.raises(ValueError, match="does not support check type"):
            validate_custom_rule_payload(
                "cell",
                [
                    {
                        "table_name": "cell_lte",
                        "column": "lte_carrierparameters_maxtxpower",
                        "rule_type": "boolean_true",
                        "rule_params": {},
                    }
                ],
            )

    def test_text_column_rejects_numeric_check(self):
        with pytest.raises(ValueError, match="does not support check type"):
            validate_rule_type_for_column("location", "town", "in_range")


class TestColumnResultKey:
    def test_key_format(self):
        assert column_result_key("cell_lte", "lte_tac") == "cell_lte.lte_tac"
