"""``SqliteD1``: a D1-shaped binding over ``sqlite3``.

The D1 repositories are the only SQL implementation in this app. Tests and
``local_server.py`` run that same SQL against this wrapper, so what is tested is
what ships. It models the slice of the D1 API the repositories use:

* ``db.prepare(sql).bind(*params)`` gives a statement with async ``first()``
  (a ``dict`` or ``None``), ``all()`` (an object with ``.results``, a list of
  ``dict``) and ``run()``.
* ``db.batch(statements)`` runs the statements in a single transaction.

Differences worth knowing: ``sqlite3.IntegrityError`` propagates unchanged, and
``PRAGMA foreign_keys = ON`` is set on connect, matching D1's default.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace


class _Statement:
    def __init__(self, conn: sqlite3.Connection, sql: str, params: tuple = ()):
        self._conn = conn
        self._sql = sql
        self._params = params

    def bind(self, *params) -> "_Statement":
        return _Statement(self._conn, self._sql, params)

    def _execute(self) -> list[dict]:
        # Always drain the cursor: an INSERT ... RETURNING is not finished (and,
        # in autocommit, not committed) until its rows have been fetched.
        cursor = self._conn.execute(self._sql, self._params)
        return [dict(row) for row in cursor.fetchall()]

    async def first(self) -> dict | None:
        rows = self._execute()
        return rows[0] if rows else None

    async def all(self) -> SimpleNamespace:
        return SimpleNamespace(results=self._execute())

    async def run(self) -> SimpleNamespace:
        self._execute()
        return SimpleNamespace(success=True)


class SqliteD1:
    """Wrap a path, ``":memory:"`` or an open ``sqlite3.Connection``.

    A connection passed in is switched to autocommit mode
    (``isolation_level = None``): ``run()`` outside a batch commits at once, and
    ``batch()`` opens an explicit transaction.
    """

    def __init__(self, path_or_conn: str | Path | sqlite3.Connection = ":memory:"):
        if isinstance(path_or_conn, sqlite3.Connection):
            self._conn = path_or_conn
        else:
            self._conn = sqlite3.connect(str(path_or_conn))
        self._conn.isolation_level = None
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def prepare(self, sql: str) -> _Statement:
        return _Statement(self._conn, sql)

    async def batch(self, statements) -> list[SimpleNamespace]:
        """Run every statement in one transaction; any error rolls all back."""
        results = []
        self._conn.execute("BEGIN")
        try:
            for statement in statements:
                statement._execute()
                results.append(SimpleNamespace(success=True))
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")
        return results

    def executescript(self, sql: str) -> None:
        """Apply a migration script (not part of the D1 binding; for tests and local dev)."""
        self._conn.executescript(sql)
