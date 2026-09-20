"""
Development settings for OmniEducationalManagement.
"""
from config.settings.base import *  # noqa: F403

DEBUG = True

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Allow Dev Tunnel and Vercel hosts
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "3lrrk4tb-8000.inc1.devtunnels.ms",
    ".vercel.app",
]

# CORS: credentials mode requires explicit origins (not wildcard)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5175",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5175",
    "https://omni-educational-management-fronten.vercel.app",
    "https://omni-educational-management-frontend.vercel.app",
    "https://3lrrk4tb-8000.inc1.devtunnels.ms",
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.devtunnels\.ms$",
]

# CSRF: trust the Dev Tunnel and Vercel origins for cookie-based auth
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5175",
    "https://omni-educational-management-fronten.vercel.app",
    "https://omni-educational-management-frontend.vercel.app",
    "https://3lrrk4tb-8000.inc1.devtunnels.ms",
]

