"""Integration test for checkpointer retention (agent/cleanup.py).

Exercises delete_idle_threads against a real async Postgres checkpointer: it
inserts a deliberately aged thread and a fresh one, runs the sweep, and asserts
the aged thread is gone from all three checkpoint tables while the fresh one
survives.

delete_idle_threads is async (the serving layer runs it on the event loop), so
the test drives it with asyncio.run, avoiding a pytest-asyncio dependency.
Requires a reachable database (DATABASE_URL, the same one docker-compose brings
up); skips cleanly when none is configured or reachable, so it is safe on a bare
checkout. Each run uses unique thread ids and removes its own rows, so it never
touches real conversation data.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg_pool import AsyncConnectionPool  # noqa: E402

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402

from nrcs_navigator.agent.cleanup import delete_idle_threads  # noqa: E402


def _psycopg_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    return url.replace("+psycopg", "", 1) if url else None


async def _insert_thread(conn, thread_id: str, ts: str) -> None:
    """Insert a minimal checkpoint plus a blob and write row for thread_id.

    Mirrors the rows the checkpointer would write for one super step, with the
    timestamp delete_idle_threads reads (checkpoint->>'ts') set to ts.
    """
    checkpoint_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata)
        VALUES (%s, '', %s, NULL, %s, '{}')
        """,
        (thread_id, checkpoint_id, f'{{"ts": "{ts}", "v": 1}}'),
    )
    await conn.execute(
        """
        INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob)
        VALUES (%s, '', 'messages', '1', 'msgpack', %s)
        """,
        (thread_id, b"x"),
    )
    await conn.execute(
        """
        INSERT INTO checkpoint_writes
            (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob)
        VALUES (%s, '', %s, %s, 0, 'messages', 'msgpack', %s)
        """,
        (thread_id, checkpoint_id, str(uuid.uuid4()), b"x"),
    )


async def _counts(conn, thread_id: str) -> tuple[int, int, int]:
    async def n(table: str) -> int:
        cur = await conn.execute(
            f"SELECT count(*) AS c FROM {table} WHERE thread_id = %s", (thread_id,)
        )
        row = await cur.fetchone()
        return row["c"]

    return await n("checkpoints"), await n("checkpoint_blobs"), await n("checkpoint_writes")


async def _run(url: str) -> None:
    try:
        pool = AsyncConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            open=False,
        )
        await pool.open()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database not reachable: {exc}")

    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    try:
        old_id = f"test-old-{uuid.uuid4()}"
        recent_id = f"test-recent-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=40)).isoformat()
        recent_ts = now.isoformat()

        async with saver.conn.connection() as conn:
            await _insert_thread(conn, old_id, old_ts)
            await _insert_thread(conn, recent_id, recent_ts)

        try:
            removed = await delete_idle_threads(saver, retention_days=30)

            # The sweep is database-wide; assert on our threads, not the total.
            assert removed >= 1
            async with saver.conn.connection() as conn:
                assert await _counts(conn, old_id) == (0, 0, 0)  # aged thread cleared
                assert await _counts(conn, recent_id) == (1, 1, 1)  # fresh untouched
        finally:
            # Leave the database as we found it regardless of outcome.
            await saver.adelete_thread(old_id)
            await saver.adelete_thread(recent_id)
    finally:
        await pool.close()


def test_delete_idle_threads_removes_only_aged_thread():
    url = _psycopg_url()
    if not url:
        pytest.skip("DATABASE_URL not set")
    asyncio.run(_run(url))
