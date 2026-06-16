"""Checkpointer retention: delete stale conversation threads.

The LangGraph PostgresSaver persists every conversation turn into three tables
(checkpoints, checkpoint_blobs, checkpoint_writes), keyed by thread_id (the
serving layer's session_id). Nothing removes them on its own, so the shared
database would grow without bound. This module provides the retention sweep the
serving app's background task runs: find threads whose most recent checkpoint is
older than a cutoff and delete them.

Kept out of the serving layer so the logic is unit-testable and reusable (from a
notebook or a future maintenance script) without standing up FastAPI. The deletion
itself is delegated to PostgresSaver.delete_thread, which clears all three tables
consistently; this module only decides which threads are stale.
"""

from datetime import datetime, timedelta, timezone

from langgraph.checkpoint.postgres import PostgresSaver


def delete_idle_threads(saver: PostgresSaver, retention_days: int) -> int:
    """Delete every thread whose newest checkpoint is older than retention_days.

    Returns the number of threads deleted. Idle threads are found with a single
    grouped query over the checkpoints table: each checkpoint row stores an
    ISO-8601 UTC timestamp at checkpoint->>'ts', and same-format UTC strings sort
    correctly lexicographically, so the cutoff comparison runs in SQL. Each stale
    thread_id is then handed to saver.delete_thread so all three checkpoint tables
    are cleaned together.

    The SELECT and the deletes borrow separate connections from the saver's pool;
    a thread that becomes active in between would, at worst, be resumed and
    immediately re-checkpointed by its next request, which is acceptable for a
    daily retention sweep.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    with saver.conn.connection() as conn:
        rows = conn.execute(
            """
            SELECT thread_id
            FROM checkpoints
            GROUP BY thread_id
            HAVING MAX(checkpoint->>'ts') < %s
            """,
            (cutoff,),
        ).fetchall()
    # The pool uses a dict_row factory, so each row is a dict keyed by column name.
    thread_ids = [row["thread_id"] for row in rows]
    for thread_id in thread_ids:
        saver.delete_thread(thread_id)
    return len(thread_ids)
