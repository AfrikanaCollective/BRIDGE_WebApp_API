# backend/config/preprocessing_profiles.py

from typing import Optional

PREPROCESSING_PROFILES = {
    "ITF": {
        "max_pixels": 1_200_000,
        "min_dpi": 150,
        "target_dpi": 200,
        "denoise": True,
        "enhance_contrast": True,
        "clahe_clip_limit": 2.0,
    },
    "COMPLEX_FORM": {
        "max_pixels": 1_500_000,
        "min_dpi": 180,
        "target_dpi": 220,
        "denoise": True,
        "enhance_contrast": True,
        "clahe_clip_limit": 2.5,
    },
    "SIMPLE_TEXT": {
        "max_pixels": 800_000,
        "min_dpi": 100,
        "target_dpi": 150,
        "denoise": False,
        "enhance_contrast": False,
        "clahe_clip_limit": 1.0,
    },
    "HANDWRITTEN": {
        "max_pixels": 1_400_000,
        "min_dpi": 200,
        "target_dpi": 240,
        "denoise": True,
        "enhance_contrast": True,
        "clahe_clip_limit": 3.0,  # More aggressive for handwriting
    }
}


def get_profile(form_type: Optional[str]) -> dict:
    """Get preprocessing profile by form type."""
    if not form_type:
        return PREPROCESSING_PROFILES["COMPLEX_FORM"]

    return PREPROCESSING_PROFILES.get(
        form_type.upper(),
        PREPROCESSING_PROFILES["COMPLEX_FORM"]
    )
