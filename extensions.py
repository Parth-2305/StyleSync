"""Shared security helpers, created once here so app.py and the blueprints can both import them."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

# CSRF: every POST must carry a secret token, so another website can't make
# your logged-in browser submit forms to us.
csrf = CSRFProtect()

# Rate limiting: counts requests per visitor (by IP) and answers 429 when a limit is exceeded.
limiter = Limiter(get_remote_address, default_limits=["300 per hour"], storage_uri="memory://")
