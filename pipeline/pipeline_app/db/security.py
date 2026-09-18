"""
Database security and provisioning DDL.

All functions operate on an existing AsyncConnection (from engine.begin())
and are idempotent -- safe to call multiple times.

Four public functions:
    ensure_extensions          -- PostGIS, pg_trgm
    ensure_grants              -- schema/table/sequence privileges for RLS user
    ensure_rls_policies        -- row-level security policies for scoped access
    ensure_performance_indexes -- imported_at, cell_iid, covering indexes
"""

import re

from sqlalchemy import text

from pipeline_app.core.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

_VALID_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

async def ensure_extensions(conn) -> None:
    """Install required PostgreSQL extensions.

    Must run before Base.metadata.create_all because ORM models
    reference Geography column types from PostGIS.
    """
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology;"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
    logger.info("PostgreSQL extensions ensured (postgis, postgis_topology, pg_trgm)")


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------

async def ensure_grants(conn, user: str) -> None:
    """Grant schema, table, and sequence privileges to the RLS user.

    Validates the user identifier against a strict regex before
    interpolation to prevent SQL injection.
    """
    if not user or not _VALID_IDENT.fullmatch(user):
        raise ValueError(f"Invalid SQL identifier for grant target: {user!r}")

    quoted = f'"{user}"'

    await conn.execute(text(
        f"GRANT USAGE, CREATE ON SCHEMA public TO {quoted};"
    ))
    await conn.execute(text(
        f"GRANT SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO {quoted};"
    ))
    await conn.execute(text(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, UPDATE ON TABLES TO {quoted};"
    ))
    await conn.execute(text(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted};"
    ))
    await conn.execute(text(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {quoted};"
    ))
    logger.info("Grants configured for %s", user)


# ---------------------------------------------------------------------------
# Row-Level Security policies
# ---------------------------------------------------------------------------

async def ensure_rls_policies(conn) -> None:
    """Enable Row-Level Security and create scope policies on entity tables.

    Idempotent: uses CREATE OR REPLACE for functions and DROP POLICY IF EXISTS
    before CREATE POLICY.

    Runtime behavior (set via session-level GUC variables):
        app.scope_mode = 'unrestricted' -> all rows visible
        app.scope_mode = 'restricted'   -> only rows matching app.scoped_cell_iids
        app.scope_mode not set          -> defaults to 'deny' (no rows visible)
    """
    # ── Helper functions that policies reference at runtime ────────────────

    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION app_scope_mode() RETURNS text
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(current_setting('app.scope_mode', true), 'deny');
        $$;
    """))

    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION app_scoped_iids() RETURNS text[]
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                ARRAY(SELECT jsonb_array_elements_text(
                    current_setting('app.scoped_cell_iids', true)::jsonb
                )),
                ARRAY[]::text[]
            );
        $$;
    """))

    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION app_allowed_location_iids() RETURNS text[]
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                ARRAY(
                    SELECT DISTINCT x.location_iid
                    FROM (
                        SELECT c.location_iid
                        FROM cell_lte c
                        WHERE c.iid = ANY(SELECT unnest(app_scoped_iids()))
                        UNION ALL
                        SELECT n.location_iid
                        FROM cell_nr n
                        WHERE n.iid = ANY(SELECT unnest(app_scoped_iids()))
                    ) x
                    WHERE x.location_iid IS NOT NULL
                ),
                ARRAY[]::text[]
            );
        $$;
    """))

    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION app_allowed_mu_lte_iids() RETURNS text[]
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                ARRAY(
                    SELECT DISTINCT c.mu_iid
                    FROM cell_lte c
                    WHERE c.iid = ANY(SELECT unnest(app_scoped_iids()))
                      AND c.mu_iid IS NOT NULL
                ),
                ARRAY[]::text[]
            );
        $$;
    """))

    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION app_allowed_mu_nr_iids() RETURNS text[]
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                ARRAY(
                    SELECT DISTINCT n.mu_iid
                    FROM cell_nr n
                    WHERE n.iid = ANY(SELECT unnest(app_scoped_iids()))
                      AND n.mu_iid IS NOT NULL
                ),
                ARRAY[]::text[]
            );
        $$;
    """))

    # ── Direct cell tables (cell_lte, cell_nr) ────────────────────────────

    for tbl in ("cell_lte", "cell_nr"):
        await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))

        await conn.execute(text(f"DROP POLICY IF EXISTS rls_{tbl} ON {tbl}"))
        await conn.execute(text(f"""
            CREATE POLICY rls_{tbl} ON {tbl} FOR SELECT USING (
                CASE (SELECT app_scope_mode())
                    WHEN 'unrestricted' THEN true
                    WHEN 'restricted' THEN iid = ANY(SELECT unnest(app_scoped_iids()))
                    ELSE false
                END
            )
        """))

        await conn.execute(text(f"DROP POLICY IF EXISTS rls_{tbl}_update ON {tbl}"))
        await conn.execute(text(f"""
            CREATE POLICY rls_{tbl}_update ON {tbl} FOR UPDATE USING (
                CASE (SELECT app_scope_mode())
                    WHEN 'unrestricted' THEN true
                    WHEN 'restricted' THEN iid = ANY(SELECT unnest(app_scoped_iids()))
                    ELSE false
                END
            )
        """))

    # ── Location (transitive via cells) ───────────────────────────────────

    await conn.execute(text("ALTER TABLE location ENABLE ROW LEVEL SECURITY"))
    await conn.execute(text("ALTER TABLE location FORCE ROW LEVEL SECURITY"))
    await conn.execute(text("DROP POLICY IF EXISTS rls_location ON location"))
    await conn.execute(text("""
        CREATE POLICY rls_location ON location FOR SELECT USING (
            CASE (SELECT app_scope_mode())
                WHEN 'unrestricted' THEN true
                WHEN 'restricted' THEN location.iid = ANY(SELECT unnest(app_allowed_location_iids()))
                ELSE false
            END
        )
    """))

    # ── MU tables (transitive via their respective cell tables) ───────────

    for tbl, allowed_fn in [
        ("mu_lte", "app_allowed_mu_lte_iids"),
        ("mu_nr", "app_allowed_mu_nr_iids"),
    ]:
        await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
        await conn.execute(text(f"DROP POLICY IF EXISTS rls_{tbl} ON {tbl}"))
        await conn.execute(text(f"""
            CREATE POLICY rls_{tbl} ON {tbl} FOR SELECT USING (
                CASE (SELECT app_scope_mode())
                    WHEN 'unrestricted' THEN true
                    WHEN 'restricted' THEN {tbl}.iid = ANY(SELECT unnest({allowed_fn}()))
                    ELSE false
                END
            )
        """))

    # ── Antenna tables (direct scoped cell_iid match) ────────────────────

    for tbl in ("cell_physical_antenna", "cell_logical_antenna"):
        await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
        await conn.execute(text(f"DROP POLICY IF EXISTS rls_{tbl} ON {tbl}"))
        await conn.execute(text(f"""
            CREATE POLICY rls_{tbl} ON {tbl} FOR SELECT USING (
                CASE (SELECT app_scope_mode())
                    WHEN 'unrestricted' THEN true
                    WHEN 'restricted' THEN {tbl}.cell_iid = ANY(SELECT unnest(app_scoped_iids()))
                    ELSE false
                END
            )
        """))

    # ── Discrepancies table ───────────────────────────────────────────────

    await conn.execute(text("ALTER TABLE discrepancies ENABLE ROW LEVEL SECURITY"))
    await conn.execute(text("ALTER TABLE discrepancies FORCE ROW LEVEL SECURITY"))

    await conn.execute(text("DROP POLICY IF EXISTS rls_discrepancies ON discrepancies"))
    await conn.execute(text("""
        CREATE POLICY rls_discrepancies ON discrepancies FOR SELECT USING (
            CASE (SELECT app_scope_mode())
                WHEN 'unrestricted' THEN true
                WHEN 'restricted' THEN discrepancies.cell_name = ANY(SELECT unnest(app_scoped_iids()))
                ELSE false
            END
        )
    """))

    await conn.execute(text("DROP POLICY IF EXISTS rls_discrepancies_update ON discrepancies"))
    await conn.execute(text("""
        CREATE POLICY rls_discrepancies_update ON discrepancies FOR UPDATE USING (
            CASE (SELECT app_scope_mode())
                WHEN 'unrestricted' THEN true
                WHEN 'restricted' THEN discrepancies.cell_name = ANY(SELECT unnest(app_scoped_iids()))
                ELSE false
            END
        )
    """))

    # ── Pipeline metadata (always visible) ────────────────────────────────

    await conn.execute(text("ALTER TABLE pipeline_metadata ENABLE ROW LEVEL SECURITY"))
    await conn.execute(text("ALTER TABLE pipeline_metadata FORCE ROW LEVEL SECURITY"))
    await conn.execute(text("DROP POLICY IF EXISTS rls_pipeline_metadata ON pipeline_metadata"))
    await conn.execute(text("""
        CREATE POLICY rls_pipeline_metadata ON pipeline_metadata FOR SELECT USING (true)
    """))

    logger.info("RLS policies configured for scoped cell access")


# ---------------------------------------------------------------------------
# Performance indexes
# ---------------------------------------------------------------------------

_RLS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_phys_antenna_cell_iid ON cell_physical_antenna (cell_iid)",
    "CREATE INDEX IF NOT EXISTS idx_log_antenna_cell_iid  ON cell_logical_antenna  (cell_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_lte_iid_cover    ON cell_lte (iid) INCLUDE (location_iid, mu_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_nr_iid_cover     ON cell_nr  (iid) INCLUDE (location_iid, mu_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_lte_mu_iid       ON cell_lte (mu_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_nr_mu_iid        ON cell_nr  (mu_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_lte_cell_iid     ON cell_lte (cell_iid)",
    "CREATE INDEX IF NOT EXISTS idx_cell_nr_cell_iid      ON cell_nr  (cell_iid)",
    "CREATE INDEX IF NOT EXISTS idx_discrepancies_cell_name ON discrepancies (cell_name)",
]

_QUERY_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_location_imported_at ON location (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_mu_lte_imported_at   ON mu_lte (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_mu_nr_imported_at    ON mu_nr (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_cell_lte_imported_at ON cell_lte (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_cell_nr_imported_at  ON cell_nr (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_cpa_imported_at      ON cell_physical_antenna (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_cla_imported_at      ON cell_logical_antenna (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_discrepancies_imported_at ON discrepancies (imported_at)",
    "CREATE INDEX IF NOT EXISTS ix_cpa_cell_iid         ON cell_physical_antenna (cell_iid)",
    "CREATE INDEX IF NOT EXISTS ix_cla_cell_iid         ON cell_logical_antenna (cell_iid)",
    "CREATE INDEX IF NOT EXISTS ix_cpa_antennadevice_iid ON cell_physical_antenna (antennadevice_iid)",
]

ALL_INDEXES = _RLS_INDEXES + _QUERY_INDEXES


async def ensure_performance_indexes(conn) -> None:
    """Create all performance indexes. Each statement is idempotent (IF NOT EXISTS).

    Merges two sources:
        - RLS policy indexes  (from db_operation.py -- covering, JOIN support)
        - Query indexes       (from ensure_indexes.py -- imported_at, antenna keys)
    """
    created = 0
    skipped = 0
    for idx_sql in ALL_INDEXES:
        try:
            await conn.execute(text(idx_sql))
            created += 1
        except Exception as e:
            skipped += 1
            logger.warning("Index skipped: %s", e)

    logger.info("Performance indexes: %d created, %d skipped", created, skipped)
