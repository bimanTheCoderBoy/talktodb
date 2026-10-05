-- =============================================================================
-- PostgreSQL Extensions and Database Initialization
-- =============================================================================

-- Note: The default database (jersey) is created by POSTGRES_DB env var
-- We need to create additional databases here

-- Create langgraph_data database if it doesn't exist
SELECT 'CREATE DATABASE langgraph_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langgraph_data')\gexec

-- Create jersey database if it doesn't exist
SELECT 'CREATE DATABASE jersey'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'jersey')\gexec

-- Create pipeline_db database for Pipeline v2
SELECT 'CREATE DATABASE pipeline_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'pipeline_db')\gexec

-- Semantic catalog + user project config (agent RANORA_CONFIG_DB_NAME default)
SELECT 'CREATE DATABASE ranora_config'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ranora_config')\gexec

-- RLS reader used by pipeline (RLS_DB_USER) and agent (DB_USER); idempotent for re-runs
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_reader') THEN
    CREATE ROLE app_reader LOGIN PASSWORD 'app_reader';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE ranora_config TO app_reader;

-- Connect to jersey and create extensions
\c jersey
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS ltree;

-- ranora_config: catalog fuzzy search (pg_trgm) + app_reader read access
\c ranora_config
CREATE EXTENSION IF NOT EXISTS pg_trgm;

GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_reader;

-- Connect to langgraph_data and create extensions
-- \c langgraph_data
-- CREATE EXTENSION IF NOT EXISTS vector;
