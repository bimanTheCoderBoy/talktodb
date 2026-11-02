-- =============================================================================
-- talkToDB — PostgreSQL databases for LangGraph + app data
-- =============================================================================

SELECT 'CREATE DATABASE langgraph_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langgraph_data')\gexec

-- App database (catalog tables and future app tables). Name overridable via TALKTODB_DB_NAME.
SELECT 'CREATE DATABASE talktodb'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'talktodb')\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_reader') THEN
    CREATE ROLE app_reader LOGIN PASSWORD 'app_reader';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE talktodb TO app_reader;

\c talktodb
CREATE EXTENSION IF NOT EXISTS pg_trgm;

GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;
