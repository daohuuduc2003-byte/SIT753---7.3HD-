import os
import sys
import tempfile

import pytest

# Point the app at a throwaway database before it is imported
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(_tmpdir, "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server  # noqa: E402

# Safety net: never run tests against the real database
assert server.DB_PATH == os.environ["DATABASE_PATH"], (
    "server.py is not reading DATABASE_PATH, refusing to run tests on the real database"
)


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.get_db() as conn:
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM members")
        conn.execute("DELETE FROM trail_reviews")
    with server.app.test_client() as c:
        yield c
