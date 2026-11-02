-- =============================================================================
-- talkToDB — PostgreSQL databases for LangGraph + app data
-- =============================================================================

SELECT 'CREATE DATABASE langgraph_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langgraph_data')\gexec

-- App database (catalog tables and future app tables). Name overridable via TALKTODB_DB_NAME.
SELECT 'CREATE DATABASE talktodb'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'talktodb')\gexec

\c talktodb
CREATE EXTENSION IF NOT EXISTS pg_trgm;
