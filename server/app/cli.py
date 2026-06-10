from __future__ import annotations

import asyncio
from dataclasses import dataclass

import typer

from app.auth import hash_password
from app.config import Settings, get_settings
from app.database import close_database, init_database
from app.database.models import DOCUMENT_MODELS, User, UserRole, UserStatus

cli = typer.Typer(help="Operational commands for CVantage server")


@dataclass(slots=True)
class IndexSyncStatus:
    collection: str
    expected: list[str]
    existing: list[str]
    missing: list[str]


async def seed_admin_account(settings: Settings) -> bool:
    if not settings.admin_email or not settings.admin_password:
        raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD must be set")

    await init_database(settings)
    try:
        normalized_email = settings.admin_email.lower().strip()
        existing_admin = await User.find_one(User.email == normalized_email)

        if existing_admin is not None:
            return False

        admin = User(
            email=normalized_email,
            password_hash=hash_password(settings.admin_password),
            full_name="Platform Admin",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        await admin.insert()
        return True
    finally:
        await close_database()


async def collect_index_sync_status(settings: Settings) -> list[IndexSyncStatus]:
    await init_database(settings)
    try:
        statuses: list[IndexSyncStatus] = []
        for model in DOCUMENT_MODELS:
            collection = model.get_motor_collection()
            collection_name = model.get_settings().name or model.__name__.lower()

            declared_indexes = getattr(getattr(model, "Settings", object()), "indexes", [])
            expected_names: list[str] = []
            for index in declared_indexes:
                document = index.document
                name = document.get("name")
                if isinstance(name, str):
                    expected_names.append(name)

            index_info = await collection.index_information()
            existing_names = sorted(index_info.keys())
            missing_names = sorted(name for name in expected_names if name not in index_info)

            statuses.append(
                IndexSyncStatus(
                    collection=collection_name,
                    expected=sorted(expected_names),
                    existing=existing_names,
                    missing=missing_names,
                )
            )

        return statuses
    finally:
        await close_database()


@cli.command("seed-admin")
def seed_admin() -> None:
    """Create a bootstrap admin user from ADMIN_EMAIL and ADMIN_PASSWORD."""

    settings = get_settings()
    try:
        created = asyncio.run(seed_admin_account(settings))
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if created:
        typer.echo("Admin user created")
    else:
        typer.echo("Admin user already exists")


@cli.command("sync-indexes")
def sync_indexes() -> None:
    """Initialize and verify Beanie indexes across all configured documents."""

    settings = get_settings()
    statuses = asyncio.run(collect_index_sync_status(settings))

    has_missing = False
    for status in statuses:
        typer.echo(f"{status.collection}: {len(status.existing)} indexes")
        if status.expected:
            typer.echo(f"  expected: {', '.join(status.expected)}")
        if status.missing:
            has_missing = True
            typer.echo(f"  missing: {', '.join(status.missing)}")

    if has_missing:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    cli()
