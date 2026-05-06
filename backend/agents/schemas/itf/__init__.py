"""ITF (Internal Transfer Form) schemas."""

from agents.config import get_form_schema

__all__ = ['get_itf_schema']


def get_itf_schema(page_number: int):
    """Get ITF schema for specific page."""
    return get_form_schema('ITF', page_number)
