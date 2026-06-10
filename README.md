# CVantage

Monorepo scaffold for the CVantage platform.

## Structure

- `server/`: Python backend (uv-managed)
- `frontend/`: React/TypeScript frontend (pnpm-managed)
- `database/`: canonical model references
- `PLAN.md`, `PROMPT.md`, `CLAUDE.md`: planning and build constraints

## Quick Start

1. Ensure Python 3.11 is installed.
2. Ensure Node.js 22 LTS and Corepack are available.
3. Sync backend dependencies:
	- `cd server`
	- `uv sync`
4. Install frontend dependencies:
	- `cd frontend`
	- `pnpm install`
5. Install commit hooks:
	- `cd ..` (repo root)
	- `pre-commit install`
