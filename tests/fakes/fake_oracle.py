"""Fake oracledb-shaped connection/cursor for testing oracle_connector.py
without a real Oracle connection or the oracledb package installed."""


class FakeLob:
    """Mimics an oracledb LOB locator: reading requires .read()."""

    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text


class FakeCursor:
    def __init__(self, connection: "FakeConnection"):
        self._connection = connection
        self._rows: list[tuple] = []

    def execute(self, sql: str, **binds):
        self._connection.calls.append((sql, binds))
        self._rows = self._connection.result_for(sql, binds)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    """`result_provider(sql, binds) -> list[tuple]` decides what each
    execute() call returns, based on inspecting the SQL/binds — tests
    supply it so each test only has to describe the schema state it
    cares about."""

    def __init__(self, result_provider):
        self._result_provider = result_provider
        self.calls: list[tuple] = []
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def result_for(self, sql: str, binds: dict) -> list[tuple]:
        return self._result_provider(sql, binds)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False
