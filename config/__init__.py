"""
Initialization for config package.
Imports celery_app so @shared_task uses this app.
"""
from config.celery import app as celery_app

__all__ = ("celery_app",)
