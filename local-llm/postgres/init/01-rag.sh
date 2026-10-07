#!/bin/bash
# Exécuté une seule fois, à la création du volume : base dédiée au RAG avec pgvector.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
  CREATE DATABASE rag;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname rag <<-SQL
  CREATE EXTENSION IF NOT EXISTS vector;
SQL
