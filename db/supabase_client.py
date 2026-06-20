"""
Shared Supabase client singleton.

All services that need Supabase storage should import `get_supabase()`
from here instead of creating their own clients. This avoids:
  - Connection churn (new HTTP session per call)
  - Import-time blocking if Supabase is unreachable
  - Duplicated configuration across services
"""

import os
from functools import lru_cache
from supabase import create_client, Client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a singleton Supabase client, lazily created on first call."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
        )
    return create_client(url, key)


# Bucket name constants — single source of truth
BUCKET_APPLICATION_DOCUMENTS = "application-documents"
BUCKET_TEST_SCRIPTS = os.getenv("SUPABASE_STORAGE_TEST_SCRIPTS_BUCKET", "test_scripts")
BUCKET_K6_RESULTS = "k6_results"
