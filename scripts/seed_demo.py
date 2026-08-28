"""Reset the database to a freshly-seeded demo state.

Drops and recreates the schema from the models, bootstraps the demo user,
then runs ingest and reconcile for the configured fixture set. Used by
`make demo-reset`; harmless to run mid-demo if the data gets mangled.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from seamly import engine as engine_module
from seamly.app import register_all
from seamly.common.db import Base, make_engine, make_sessionmaker
from seamly.config import get_settings
from seamly.modules import auth
from seamly.modules.ledger.models import Customer


async def reset_and_seed() -> tuple[int, int]:
    settings = get_settings()
    db_engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(db_engine)

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    app_engine = engine_module.new_engine(actor="demo-reset", role="admin")
    register_all(app_engine)

    async with sessionmaker() as session:
        await auth.handle_bootstrap_demo_user(session, {})
        await session.commit()
        ingest_result = await app_engine.dispatch(session, "ingest.load", {})
        if ingest_result.is_err:
            err = ingest_result.error_or_raise()
            print(f"SEED FAIL: {err.code}: {err.message}", file=sys.stderr)
            raise SystemExit(1)
        reconcile_result = await app_engine.dispatch(session, "reconcile.run", {})
        if reconcile_result.is_err:
            err = reconcile_result.error_or_raise()
            print(f"SEED FAIL: {err.code}: {err.message}", file=sys.stderr)
            raise SystemExit(1)
        priced = int((reconcile_result.value or {}).get("priced", 0))
        customers = await session.scalar(select(func.count()).select_from(Customer))
        await session.commit()

    await db_engine.dispose()
    return int(customers or 0), priced


def main() -> int:
    customers, priced = asyncio.run(reset_and_seed())
    print(f"demo reset: {customers} customers ingested, {priced} exceptions priced")
    print("log in as cfo@kestrel.example / demo-secret")
    return 0


if __name__ == "__main__":
    sys.exit(main())
