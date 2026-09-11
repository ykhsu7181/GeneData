"""Production settings for the filemanager project."""

import os

from .settings import *


def required_environment(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required production environment variable is missing: {name}")
    return value


DEBUG = False
SECRET_KEY = required_environment("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = ["riceome.hzau.edu.cn", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("GENEDATA_DB_NAME", "gene_manage"),
        "USER": os.environ.get("GENEDATA_DB_USER", "gene_user"),
        "PASSWORD": required_environment("GENEDATA_DB_PASSWORD"),
        "HOST": os.environ.get("GENEDATA_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("GENEDATA_DB_PORT", "3307"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

MANUAL_FILES_DIR = os.environ.get(
    "GENEDATA_MANUAL_FILES_DIR",
    "/home/labuser/rdcheng/gd/manual_files",
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": os.environ.get(
                "GENEDATA_LOG_PATH",
                "/home/labuser/rdcheng/gd/django2/filemanager.log",
            ),
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "files": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

STATIC_ROOT = os.environ.get("GENEDATA_STATIC_ROOT", "/var/www/static/")

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = ["https://riceome.hzau.edu.cn"]
CORS_ALLOW_CREDENTIALS = True
