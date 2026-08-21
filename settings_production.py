"""
Production settings for filemanager project.
"""

from .settings import *
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Production hosts
ALLOWED_HOSTS = ['riceome.hzau.edu.cn', 'localhost', '127.0.0.1']

# Production database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gene_manage',
        'USER': 'gene_user',
        'PASSWORD': 'GeneManage123@',  # Use production password
        'HOST': '127.0.0.1',
        'PORT': '3307',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# Production file paths
MANUAL_FILES_DIR = '/home/labuser/rdcheng/gd/manual_files'

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/filemanager.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'files': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Static files configuration for production
STATIC_ROOT = '/var/www/static/'

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "https://riceome.hzau.edu.cn",
]

# Ensure CORS allows credentials if needed
CORS_ALLOW_CREDENTIALS = True
