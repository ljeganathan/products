"""Bootstrap the first `product_owner` login (CLAUDE.md §5) — there's no signup flow
for the platform super-admin, so this is the only way to create one.

Run from `backend/`:  python -m scripts.create_superuser

Uses the superuser `DATABASE_URL` (migration connection), not the app's RLS-constrained
`APP_DATABASE_URL`: this is an out-of-band operator tool, not a request path, and a
`product_owner` row (tenant_id IS NULL) can only satisfy the RLS policy's
`is_platform_admin` branch anyway.
"""

import asyncio
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Role, User  # noqa: E402

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,60}$")


def _prompt_user_id() -> str:
    while True:
        user_id = input("Product owner User ID (not an email): ").strip()
        if _USER_ID_RE.match(user_id):
            return user_id
        print("  Must be 2-60 chars, letters/digits/underscore/hyphen only.")


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("  Password must be at least 8 characters.")
            continue
        if password != getpass.getpass("Confirm password: "):
            print("  Passwords did not match, try again.")
            continue
        return password


async def main() -> None:
    user_id = _prompt_user_id()
    name = input("Full name: ").strip() or user_id
    password = _prompt_password()

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_maker() as session:
            existing = (
                await session.execute(select(User).where(User.user_id == user_id))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"User ID '{user_id}' is already taken. Aborting.")
                raise SystemExit(1)

            role = (
                await session.execute(select(Role).where(Role.code == "product_owner"))
            ).scalar_one_or_none()
            if role is None:
                print("No 'product_owner' role found — has `alembic upgrade head` been run?")
                raise SystemExit(1)

            session.add(
                User(
                    tenant_id=None,
                    user_id=user_id,
                    password_hash=hash_password(password),
                    role_id=role.id,
                    name=name,
                    is_active=True,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()

    print(f"\nCreated product_owner '{user_id}'. They can now log in at /login.")


if __name__ == "__main__":
    asyncio.run(main())
