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

SELECT 'CREATE DATABASE "user"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '"user"')\gexec


-- RLS reader used by pipeline (RLS_DB_USER); idempotent for re-runs / old volumes
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_reader') THEN
    CREATE ROLE app_reader LOGIN PASSWORD 'app_reader';
  END IF;
END
$$;

-- Connect to jersey and create extensions
\c jersey
-- CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS ltree;

-- Connect to langgraph_data and create extensions
-- \c langgraph_data
-- CREATE EXTENSION IF NOT EXISTS vector;


