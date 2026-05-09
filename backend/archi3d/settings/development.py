"""Development settings for Archi3D."""

from .base import *  # noqa: F401,F403

DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver"]

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
ARCHI3D["REQUIRE_AUTH_FOR_DESIGN"] = env("REQUIRE_AUTH_FOR_DESIGN")
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
