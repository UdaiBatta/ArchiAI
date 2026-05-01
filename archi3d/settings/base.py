"""Shared Django settings for Archi3D."""

from pathlib import Path

import environ

# Base Directory ───────────────────────────────────────────────────────────────
# backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load Environment Variables ───────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "testserver"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    FRONTEND_URL=(str, "http://localhost:5173"),
    REDIS_URL=(str, ""),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/1"),
    CELERY_RESULT_BACKEND=(str, "redis://localhost:6379/1"),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
    CELERY_TASK_EAGER_PROPAGATES=(bool, False),
    OLLAMA_HOST=(str, "http://localhost:11434"),
    OLLAMA_MODEL=(str, "llama3.2"),
    RAG_TOP_K=(int, 5),
    HYPAR_API_URL=(str, ""),
    HYPAR_API_TOKEN=(str, ""),
    REQUIRE_AUTH_FOR_DESIGN=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

# Core Security ────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-change-in-production")

# Installed Applications ───────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    "corsheaders",
    "apps.accounts.apps.AccountsConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.design.apps.DesignConfig",
    "apps.health.apps.HealthConfig",
]

# Middleware ───────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "archi3d.urls"

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
ASGI_APPLICATION = "archi3d.asgi.application"

# Database ─────────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.CustomUser"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@archiai.dev")
FRONTEND_URL = env("FRONTEND_URL")

MEDIA_URL = "/outputs/"
MEDIA_ROOT = BASE_DIR / env("OUTPUTS_DIR", default="outputs")

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": env.channels_url("REDIS_URL"),
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = env("CELERY_TASK_EAGER_PROPAGATES")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

ARCHI3D = {
    "BYLAWS_DIR": BASE_DIR / env("BYLAWS_DIR", default="bylaws"),
    "KNOWLEDGE_DIR": BASE_DIR / env("KNOWLEDGE_DIR", default="knowledge"),
    "OUTPUTS_DIR": BASE_DIR / env("OUTPUTS_DIR", default="outputs"),
    "OLLAMA_HOST": env("OLLAMA_HOST"),
    "OLLAMA_MODEL": env("OLLAMA_MODEL"),
    "RAG_TOP_K": env("RAG_TOP_K"),
    "HYPAR_API_URL": env("HYPAR_API_URL"),
    "HYPAR_API_TOKEN": env("HYPAR_API_TOKEN"),
    "GRAPH2PLAN_ROOT": BASE_DIR / "Graph2plan-master",
    "JOB_SYNC_EXECUTION": False,
    "KNOWLEDGE_SOURCE_DIR": BASE_DIR / "knowledge" / "source_docs",
    "KNOWLEDGE_OUTPUT_FILE": BASE_DIR / "knowledge" / "raw" / "ingested_documents.json",
    "INGESTION_MAX_PDF_PAGES": 300,
    "INGESTION_MAX_PDF_CHARS": 1500000,
    "REQUIRE_AUTH_FOR_DESIGN": env("REQUIRE_AUTH_FOR_DESIGN"),
}
