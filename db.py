"""Supabase clients. Only the server ever holds these keys; the browser never talks to Supabase."""
import os

from supabase import create_client


def is_configured():
    return all(os.getenv(k) for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"))


def auth_client():
    """A FRESH anon client per login/signup. supabase-py remembers the last signed-in user
    inside the client, so sharing one between visitors would mix their sessions up."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


_data_client = None


def data_client():
    """Service-role client for reading/writing wardrobe data. It bypasses row-level security,
    so every query MUST filter by the logged-in user's id (see the helpers in later files)."""
    global _data_client
    if _data_client is None:
        _data_client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    return _data_client
