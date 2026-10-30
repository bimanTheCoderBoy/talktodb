-- =============================================================================
-- talkToDB — PostgreSQL databases for LangGraph + semantic catalog
-- =============================================================================

SELECT 'CREATE DATABASE langgraph_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langgraph_data')\gexec

-- Semantic catalog (tables from manage_db_context / ORM). Name overridable via CATALOG_DB_NAME.
SELECT 'CREATE DATABASE talktodb_config'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'talktodb_config')\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_reader') THEN
    CREATE ROLE app_reader LOGIN PASSWORD 'app_reader';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE talktodb_config TO app_reader;

\c talktodb_config
CREATE EXTENSION IF NOT EXISTS pg_trgm;

GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;
