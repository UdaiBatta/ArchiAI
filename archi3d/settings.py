"""
archi3d/settings.py — Django Configuration
==========================================

HOW THIS FILE WORKS:
- All settings are read from the .env file using django-environ
- Copy .env.example to .env and fill in values before starting
- If a value is missing from .env, the default shown here is used

SETTINGS REFERENCE:
  https://docs.djangoproject.com/en/4.2/ref/settings/

DEBUGGING TIPS:
- If SECRET_KEY error: copy .env.example to .env and set a secret key
- If database errors: run `python manage.py migrate` first
- If app not found: check INSTALLED_APPS list and app label in apps.py
"""

from pathlib import Path
import environ

# ── Base Directory ─────────────────────────────────────────────────────────────
# BASE_DIR = d:/My projects/Archi3D/backend/
# All file paths in settings are resolved relative to this.
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Load Environment Variables ─────────────────────────────────────────────────
# django-environ reads your .env file and makes values available via env()
env = environ.Env(
    # Declare types and defaults for each variable
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    OLLAMA_HOST=(str, "http://localhost:11434"),
    OLLAMA_MODEL=(str, "llama3.2"),
    RAG_TOP_K=(int, 5),
    HYPAR_API_URL=(str, ""),
    HYPAR_API_TOKEN=(str, ""),
)

# Read the .env file (if it exists — falls back to env variables)
environ.Env.read_env(BASE_DIR / ".env")

# ── Core Security ──────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-change-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ── Installed Applications ─────────────────────────────────────────────────────
# Order matters: Django processes middleware and signals in this order.
INSTALLED_APPS = [
    # Django built-ins (required)
    "django.contrib.admin",         # Admin UI at /admin/
    "django.contrib.auth",          # Authentication framework
    "django.contrib.contenttypes",  # Content type framework (needed by admin)
    "django.contrib.sessions",      # Session framework
    "django.contrib.messages",      # Flash messages
    "django.contrib.staticfiles",   # Static file serving

    # Third-party
    "rest_framework",               # Django REST Framework — API layer
    "corsheaders",                  # CORS headers for React frontend

    # Our apps
    "apps.design.apps.DesignConfig",   # Main design pipeline app
    "apps.health.apps.HealthConfig",   # Health check endpoint
]

# ── Middleware ─────────────────────────────────────────────────────────────────
# Middleware runs on every request/response (in order for request, reverse for response)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",         # Must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "archi3d.urls"

# ── Templates ──────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "archi3d.wsgi.application"

# ── Database ───────────────────────────────────────────────────────────────────
# Default: SQLite (stored in backend/db.sqlite3)
# Change DATABASE_URL in .env to switch to PostgreSQL in production
DATABASES = {
    "default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

# ── Password Validation ────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Localisation ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"      # IST — change to your timezone if needed
USE_I18N = True
USE_TZ = True

# ── Static Files ───────────────────────────────────────────────────────────────
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Media Files (generated outputs: GLB, Hypar JSON) ──────────────────────────
MEDIA_URL = "/outputs/"
MEDIA_ROOT = BASE_DIR / env("OUTPUTS_DIR", default="outputs")

# ── CORS (Cross-Origin Resource Sharing) ──────────────────────────────────────
# Allows the React frontend (on a different port) to call our Django API
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# ── Django REST Framework ──────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # Return JSON by default (not HTML browsable API in production)
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",  # Keep for dev (nice UI)
    ],
    # Return JSON parsing by default
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    # Pagination — configured per view in Phase 4 (not set globally to avoid W001 warning)
}

# ── Archi3D Custom Settings ────────────────────────────────────────────────────
# These are accessed in services via:  from django.conf import settings
ARCHI3D = {
    "BYLAWS_DIR": BASE_DIR / env("BYLAWS_DIR", default="bylaws"),
    "KNOWLEDGE_DIR": BASE_DIR / env("KNOWLEDGE_DIR", default="knowledge"),
    "OUTPUTS_DIR": BASE_DIR / env("OUTPUTS_DIR", default="outputs"),
    "OLLAMA_HOST": env("OLLAMA_HOST"),
    "OLLAMA_MODEL": env("OLLAMA_MODEL"),
    "RAG_TOP_K": env("RAG_TOP_K"),
    "HYPAR_API_URL": env("HYPAR_API_URL"),
    "HYPAR_API_TOKEN": env("HYPAR_API_TOKEN"),
}
