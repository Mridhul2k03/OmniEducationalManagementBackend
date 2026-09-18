"""
Development settings for OmniEducationalManagement.
"""
from config.settings.base import *  # noqa: F403

DEBUG = True

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Less restrictive CORS in local dev
CORS_ALLOW_ALL_ORIGINS = True
