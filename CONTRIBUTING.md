# Contributing

## Setup

1. Install backend dependencies: `cd server && uv sync`
2. Install frontend dependencies: `cd frontend && pnpm install`
3. Install pre-commit hooks at repo root: `pre-commit install`

## Commit Workflow

- Hooks run on commit and block commits on failures.
- Run all hooks manually when needed:
  - `pre-commit run --all-files`

## Commit Messages

Use conventional commits with scope, for example:

- `feat(server): add health endpoints (#12)`
- `fix(frontend): handle refresh retry loop (#34)`
