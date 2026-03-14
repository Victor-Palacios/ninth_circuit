"""Shared Supabase client setup."""

from supabase import create_client, Client

from lib.config import SUPABASE_URL, get_supabase_secret_key


def get_client() -> Client:
    """Create and return a Supabase client using the service-role key."""
    url = SUPABASE_URL
    if not url:
        raise RuntimeError("SUPABASE_URL is not set.")
    key = get_supabase_secret_key()
    return create_client(url, key)
