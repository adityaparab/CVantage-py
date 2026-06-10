from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app, create_app


def _iter_api_routes() -> Iterator[APIRoute]:
    for route in app.routes:
        if (
            isinstance(route, APIRoute)
            and route.path.startswith("/api/v1")
            and not route.path.startswith("/api/v1/test-")
        ):
            yield route


def test_every_api_route_has_summary_and_description() -> None:
    missing: list[str] = []
    for route in _iter_api_routes():
        if not route.summary or not route.description:
            missing.append(f"{route.path} [{','.join(sorted(route.methods or []))}]")

    assert not missing, f"Routes missing summary/description: {missing}"


def test_every_api_route_has_success_response_example() -> None:
    missing: list[str] = []
    for route in _iter_api_routes():
        schema = app.openapi()["paths"][route.path]
        for method in sorted(route.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue

            operation = schema[method.lower()]
            responses = operation.get("responses", {})
            success_codes = [code for code in responses if str(code).startswith("2")]
            if not success_codes:
                missing.append(f"{route.path} [{method}] has no success response")
                continue

            has_example = False
            for code in success_codes:
                content = responses[str(code)].get("content", {})
                app_json = content.get("application/json", {})
                schema_ref = app_json.get("schema", {})

                has_schema_example = False
                if "$ref" in schema_ref:
                    ref = str(schema_ref["$ref"])
                    if ref.startswith("#/components/schemas/"):
                        schema_name = ref.rsplit("/", maxsplit=1)[-1]
                        schema = (
                            app.openapi()
                            .get("components", {})
                            .get("schemas", {})
                            .get(schema_name, {})
                        )
                        has_schema_example = "example" in schema or "examples" in schema

                if "example" in app_json or "examples" in app_json or has_schema_example:
                    has_example = True
                    break

            if not has_example:
                missing.append(f"{route.path} [{method}] has no success example")

    assert not missing, "\n".join(missing)


@pytest.mark.asyncio
async def test_openapi_endpoint_returns_json() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["openapi"].startswith("3.1")


def test_docs_disabled_in_production_when_not_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SWAGGER_ENABLED", raising=False)
    get_settings.cache_clear()

    try:
        production_app = create_app()
        assert production_app.docs_url is None
        assert production_app.redoc_url is None
        assert production_app.openapi_url is None
    finally:
        get_settings.cache_clear()
