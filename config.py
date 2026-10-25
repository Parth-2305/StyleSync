"""Startup safety checks. The app refuses to start if its secrets are missing, still placeholders, or look wrong,
so a misconfigured copy can never run half-secure. Only variable NAMES are ever printed, never values."""
import base64
import json
import os
from urllib.parse import urlparse

IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"  # set this on the real server: turns on HTTPS-only cookies + HSTS
REQUIRED = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "FLASK_SECRET_KEY")


def _jwt_role(key):
    """Legacy Supabase keys are JWTs whose payload says role=anon or role=service_role."""
    try:
        payload = key.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
    except (IndexError, ValueError):
        return None


def check_environment():
    problems = []
    for name in REQUIRED:
        value = os.getenv(name, "")
        if not value or "PASTE" in value or value.startswith("your-") or value == "change-me":
            problems.append(f"{name} is missing or still a placeholder")
    if len(os.getenv("FLASK_SECRET_KEY", "")) < 32:
        problems.append('FLASK_SECRET_KEY must be 32+ characters (make one: python -c "import secrets; print(secrets.token_hex(32))")')
    if urlparse(os.getenv("SUPABASE_URL", "")).scheme != "https":
        problems.append("SUPABASE_URL must start with https://")

    anon, service = os.getenv("SUPABASE_ANON_KEY", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if anon and anon == service:
        problems.append("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are the same value")
    # Catch swapped keys: the powerful key must never sit in the wrong place.
    if (anon.startswith("eyJ") and _jwt_role(anon) != "anon") or anon.startswith("sb_secret_"):
        problems.append("SUPABASE_ANON_KEY does not look like an anon/publishable key (keys swapped?)")
    if (service.startswith("eyJ") and _jwt_role(service) != "service_role") or service.startswith("sb_publishable_"):
        problems.append("SUPABASE_SERVICE_ROLE_KEY does not look like a service_role/secret key (keys swapped?)")
    if IS_PRODUCTION and os.getenv("FLASK_DEBUG") == "1":
        problems.append("FLASK_DEBUG=1 must never be set in production (it allows remote code execution)")

    if bool(os.getenv("VAPID_PUBLIC_KEY")) != bool(os.getenv("VAPID_PRIVATE_KEY")):
        problems.append("VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY must be set together (or both left out to turn push off)")
    if problems:
        raise SystemExit("Startup blocked, fix your .env file:\n  - " + "\n  - ".join(problems))
