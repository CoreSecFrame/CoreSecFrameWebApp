# modules/core/__init__.py
"""
Core module for CoreSecFrame webapp
Provides base classes and utilities for security modules
"""

from .base import ToolModule, GetModule, PackageManager
from .colors import Colors

__all__ = ['ToolModule', 'GetModule', 'PackageManager', 'Colors']

# Version information
__version__ = '1.0.0'
__author__ = 'CoreSecFrame Team'