This document contains references to ReviewLens

# Architecture Brief

ReviewLens
uses a React/Vite frontend and a FastAPI backend.

The backend exposes a REST API documented with OpenAPI.

The database is PostgreSQL. Application persistence uses SQLAlchemy. Migrations use Alembic.

It is a public tool, there is no authentication.

The system should remain a modular monolith unless a future application clearly requires service separation.
