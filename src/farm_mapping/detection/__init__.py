"""Replaceable, offline detection backends; no NiceGUI dependency."""
from .baseline import ColorBaseline
from .base import DetectionResult, DetectionSettings, accept_proposals

__all__ = ['ColorBaseline', 'DetectionResult', 'DetectionSettings', 'accept_proposals']
