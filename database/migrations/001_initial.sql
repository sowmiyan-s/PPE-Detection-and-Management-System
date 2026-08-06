-- Migration 001 – initial schema
-- Idempotent: wraps the full schema creation.
-- Usage: psql -U ppe_user -d ppe_db -f database/migrations/001_initial.sql

\echo 'Applying migration 001 – initial schema …'
\i database/schema.sql
\echo 'Migration 001 complete.'
