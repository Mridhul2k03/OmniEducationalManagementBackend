"""
Development settings for OmniEducationalManagement.
"""
from config.settings.base import *  # noqa: F403

DEBUG = True

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Credentials with cookies requires explicit origins/regex, not wildcard
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
