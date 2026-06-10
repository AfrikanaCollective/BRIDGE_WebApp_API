# backend/services/preprocessing.py

import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class AdaptivePreprocessor:
    """Intelligent preprocessing with configurable profiles."""

    # Default profile (fallback)
    DEFAULT_PROFILE = {
        "max_pixels": 1_500_000,
        "min_dpi": 150,
        "target_dpi": 200,
        "denoise": True,
        "enhance_contrast": True,
        "clahe_clip_limit": 2.0,
    }

    def __init__(self, profile: Optional[Dict] = None):
        """
        Initialize with optional preprocessing profile.

        Args:
            profile: Dict with keys: max_pixels, min_dpi, target_dpi,
                    denoise, enhance_contrast, clahe_clip_limit
        """
        self.profile = profile or self.DEFAULT_PROFILE

        # Validate profile keys
        required_keys = {"max_pixels", "min_dpi", "target_dpi", "denoise",
                         "enhance_contrast", "clahe_clip_limit"}
        if not required_keys.issubset(self.profile.keys()):
            missing = required_keys - set(self.profile.keys())
            raise ValueError(f"Profile missing keys: {missing}")

        logger.info(f"Initialized AdaptivePreprocessor with profile: {self.profile}")

    def calculate_optimal_dimensions(
            self,
            image: Image.Image,
            current_dpi: int = 300
    ) -> Tuple[int, int, int]:
        """
        Calculate optimal dimensions while preserving aspect ratio.

        Args:
            image: PIL Image
            current_dpi: Original DPI of the image

        Returns:
            Tuple of (width, height, adjusted_dpi)
        """
        w, h = image.size
        total_pixels = w * h
        max_pixels = self.profile["max_pixels"]
        min_dpi = self.profile["min_dpi"]

        # If already within limits, return original
        if total_pixels <= max_pixels:
            logger.debug(
                f"Image within limits: {total_pixels:,} ≤ {max_pixels:,} pixels"
            )
            return w, h, current_dpi

        # Calculate scale factor to reach max_pixels
        scale = np.sqrt(max_pixels / total_pixels)

        new_w = int(w * scale)
        new_h = int(h * scale)
        new_dpi = int(current_dpi * scale)

        logger.debug(
            f"Scaling: {w}×{h} @ {current_dpi}dpi → {new_w}×{new_h} @ {new_dpi}dpi"
        )

        # Ensure minimum DPI
        if new_dpi < min_dpi:
            dpi_scale = min_dpi / new_dpi
            new_w = int(new_w * dpi_scale)
            new_h = int(new_h * dpi_scale)
            new_dpi = min_dpi

            logger.debug(
                f"Enforcing minimum DPI: adjusted to {new_w}×{new_h} @ {new_dpi}dpi"
            )

        logger.info(
            f"Resolution optimized: {w}×{h} ({total_pixels:,}px) → "
            f"{new_w}×{new_h} ({new_w * new_h:,}px) @ {new_dpi}dpi"
        )

        return new_w, new_h, new_dpi

    def preprocess(
            self,
            image: Optional[Image.Image] = None,
            image_path: Optional[str] = None,
            current_dpi: int = 300,
    ) -> Image.Image:
        """
        Comprehensive preprocessing pipeline using profile settings.

        Args:
            image: PIL Image object (preferred)
            image_path: Path to image file (alternative)
            current_dpi: Original DPI

        Returns:
            Preprocessed PIL Image
        """
        # Load image if path provided
        if image is None and image_path is None:
            raise ValueError("Provide either image or image_path")

        if image is None:
            image = Image.open(image_path).convert('RGB')
            logger.debug(f"Loaded image from {image_path}: {image.size}")

        # Step 1: Adaptive resolution
        new_w, new_h, adj_dpi = self.calculate_optimal_dimensions(
            image, current_dpi
        )

        if (new_w, new_h) != image.size:
            image = image.resize(
                (new_w, new_h),
                Image.Resampling.LANCZOS
            )
            logger.debug(f"Resized to {image.size}")

        # Step 2: Denoise (if enabled)
        if self.profile["denoise"]:
            image = self._denoise(image)
            logger.debug("Denoising applied")

        # Step 3: Enhance faint text (if enabled)
        if self.profile["enhance_contrast"]:
            image = self._enhance_faint_text(image)
            logger.debug("Contrast enhancement applied")

        # Step 4: Normalize brightness
        image = self._normalize_brightness(image)
        logger.debug("Brightness normalization applied")

        logger.info(f"Preprocessing complete: {image.size}, dtype={image.mode}")
        return image

    def _denoise(self, image: Image.Image) -> Image.Image:
        """
        Remove compression artifacts while preserving text.
        Uses Non-Local Means Denoising.
        """
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        denoised = cv2.fastNlMeansDenoisingColored(
            img_cv,
            h=10,  # Filter strength for luminance
            hForColorComponents=10,
            templateWindowSize=7,
            searchWindowSize=21
        )

        return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))

    def _enhance_faint_text(self, image: Image.Image) -> Image.Image:
        """
        Enhance light grey freetext using CLAHE.
        Uses profile-defined clip limit.
        """
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Convert to LAB (better for contrast enhancement)
        lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE to luminance channel
        clahe = cv2.createCLAHE(
            clipLimit=self.profile["clahe_clip_limit"],
            tileGridSize=(8, 8)
        )
        l_enhanced = clahe.apply(l)

        # Merge back
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced_cv = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        return Image.fromarray(cv2.cvtColor(enhanced_cv, cv2.COLOR_BGR2RGB))

    def _normalize_brightness(self, image: Image.Image) -> Image.Image:
        """
        Normalize brightness using percentile-based approach.
        Preserves faint text without over-processing.
        """
        img_array = np.array(image, dtype=np.float32)

        # Calculate brightness
        brightness = np.mean(img_array, axis=2)

        # Use 2nd and 98th percentile for stretching
        p2, p98 = np.percentile(brightness, [2, 98])

        if p98 - p2 > 0:
            normalized = (img_array - p2) / (p98 - p2)
            normalized = np.clip(normalized * 255, 0, 255)
            return Image.fromarray(normalized.astype(np.uint8))

        return image
