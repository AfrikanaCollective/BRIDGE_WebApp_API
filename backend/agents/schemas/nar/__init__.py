"""NAR (Neonatal Activity Record) schemas."""

from agents.config import get_form_schema

__all__ = ['get_nar_schema']


def get_nar_schema(page_number: int):
    """Get NAR schema for specific page."""
    return get_form_schema('NAR', page_number)
