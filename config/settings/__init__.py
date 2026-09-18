"""
Settings package for OmniEducationalManagement.
Defaults to development settings if not explicitly specified.
"""
import os

# Default to development settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
