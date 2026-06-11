# backend/config/preprocessing_profiles.py

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PreprocessingProfile:
    """Preprocessing configuration with JPEG support."""
    name: str = "DEFAULT"
    max_pixels: int = 1_800_000  # HANDWRITTEN default
    min_dpi: int = 150
    target_dpi: int = 240  # HANDWRITTEN default
    denoise: bool = True
    enhance_contrast: bool = True
    clahe_clip_limit: float = 1.8  # HANDWRITTEN default
    target_min_pixels: int = 600_000
    target_max_pixels: int = 1_200_000
    denoise_h: int = 6  # HANDWRITTEN default - lighter for preserving detail
    denoise_template_window: int = 7
    denoise_search_window: int = 21
    clahe_tile_grid_size: Tuple[int, int] = (8, 8)
    brightness_percentile_lower: int = 2
    brightness_percentile_upper: int = 98
    # JPEG-specific: Set denoise_h higher; will be auto-reduced for JPEG
    jpeg_denoise_reduction: float = 0.7  # Multiply h by this for JPEG


PROFILES = {
    "HANDWRITTEN": {
        "max_pixels": 1_800_000,
        "target_dpi": 240,
        "denoise": True,
        "denoise_h": 6,  # Light denoising to preserve handwriting
        "enhance_contrast": True,
        "clahe_clip_limit": 1.8,
    },
    "ITF": {
        "max_pixels": 1_500_000,
        "target_dpi": 220,
        "denoise": True,
        "denoise_h": 10,
        "enhance_contrast": True,
        "clahe_clip_limit": 2.5,
    },
    "COMPLEX_FORM": {
        "max_pixels": 1_500_000,
        "target_dpi": 220,
        "denoise": True,
        "denoise_h": 10,  # Will be reduced to 7 for JPEG
        "enhance_contrast": True,
        "clahe_clip_limit": 2.5,  # Will be reduced to 1.5 for JPEG
    },
    "SIMPLE_TEXT": {
        "max_pixels": 1_200_000,
        "target_dpi": 200,
        "denoise": True,
        "denoise_h": 8,
        "enhance_contrast": True,
        "clahe_clip_limit": 2.0,
    },
}


def get_profile(form_type: str = "HANDWRITTEN") -> dict:
    """
    Get preprocessing profile by form type.

    Args:
        form_type: Type of form (COMPLEX_FORM, SIMPLE_TEXT, HANDWRITTEN)

    Returns:
        Profile dictionary with preprocessing settings

    Raises:
        ValueError: If form_type not found in PROFILES
    """
    form_type = form_type.upper()
    if form_type not in PROFILES:
        raise ValueError(
            f"Unknown form type: {form_type}. "
            f"Available: {', '.join(PROFILES.keys())}"
        )
    return PROFILES[form_type]


def get_all_profiles() -> dict:
    """Get all available preprocessing profiles."""
    return PROFILES.copy()
