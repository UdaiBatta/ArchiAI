"""Compatibility entry point for Archi3D settings.

Importing ``archi3d.settings`` loads the development settings by default so
legacy entry points keep working while the project migrates to the split
settings package.
"""

from .development import *  # noqa: F401,F403
