# backend/services/preprocessing.py

import cv2
import time
import logging
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Union, Optional

from config.settings import settings
from config.preprocessing_profiles import get_profile
from config.preprocessing_profiles import PreprocessingProfile

logger = logging.getLogger(__name__)


class AdaptivePreprocessor:
    """
    Unified preprocessing pipeline for medical forms.

    Integrates:
    - JPEG format detection for adaptive processing
    - Adaptive resolution scaling
    - Adaptive denoising (lighter for JPEG)
    - Adaptive contrast enhancement (lighter for JPEG)
    - Brightness normalization (percentile-based)
    - Final image resize for model input

    Targets: ~600k-1.2M pixels, 150-244 DPI
    Default Profile: HANDWRITTEN (preserves fine details)
    """

    def __init__(self, profile: PreprocessingProfile):
        """
        Initialize preprocessor with configuration profile.

        Args:
            profile: PreprocessingProfile instance (ITF, COMPLEX_FORM, SIMPLE_TEXT, HANDWRITTEN)
        """
        self.profile = profile
        self.logger = logger
        self._is_jpeg = False  # Track if input is JPEG for adaptive processing

    def preprocess(
            self,
            image: Union[Image.Image, str, np.ndarray],
            current_dpi: int = 300,
            resize_to_width: Optional[int] = 1200,
            save_to_temp: bool = False,
            original_filename: Optional[str] = None,
            simple_resize_only: bool = False,
            scale_factor: Optional[float] = None
    ) -> Union[Image.Image, str]:
        """
        Full preprocessing pipeline: load → scale → denoise → enhance → normalize → resize.

        JPEG-aware processing:
        - Detects JPEG input automatically
        - Reduces denoise strength (h parameter) for JPEG
        - Reduces CLAHE clip limit for JPEG
        - Prevents over-smoothing and blur artifacts

        Args:
            image: PIL Image, file path (str), or numpy array
            current_dpi: Current DPI of the image (default: 300)
            resize_to_width: Final resize width for model input (default: 1200).
                           If None, skip final resize step.
            save_to_temp: If True, saves resized image to UPLOAD_TEMP_DIR with original_filename.
                         Returns file path instead of PIL Image.
            original_filename: Required if save_to_temp=True. Used to preserve filename in temp dir.
            simple_resize_only: If True, skips all processing (denoising, contrast, brightness)
                               and resizes to exactly resize_to_width pixels wide. PNG only.
            scale_factor: Pre-specified scale factor for adaptive resolution scaling,
                         bypassing the pixel-range auto-calculation. Ignored when
                         simple_resize_only=True.

        Returns:
            PIL Image (default) or str (if save_to_temp=True)
        """
        t_total_start = time.time()

        # Track original filename for later use
        source_filename = None
        if isinstance(image, str):
            source_filename = Path(image).name
        elif original_filename:
            source_filename = original_filename

        # ==================== STEP 1: DETECT JPEG FORMAT ====================
        self._is_jpeg = self._detect_jpeg_format(image)
        if self._is_jpeg:
            self.logger.info("🖼️  JPEG format detected - using optimized settings")

        # ==================== STEP 2: LOAD IMAGE ====================
        t_load_start = time.time()
        if isinstance(image, str):
            pil_image = Image.open(image).convert("RGB")
            input_source = image
        elif isinstance(image, Path):
            pil_image = Image.open(str(image)).convert("RGB")
            input_source = str(image)
        elif isinstance(image, Image.Image):
            pil_image = image.convert("RGB") if image.mode != "RGB" else image
            input_source = "PIL Image (in-memory)"
        elif isinstance(image, np.ndarray):
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            pil_image = Image.fromarray(image_rgb, mode="RGB")
            input_source = "numpy array"
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")

        load_time = time.time() - t_load_start
        self.logger.debug(
            f"Loaded image from {input_source}: {pil_image.size} "
            f"({pil_image.size[0] * pil_image.size[1]:,} pixels) in {load_time:.3f}s"
        )

        # ==================== SIMPLE RESIZE PATH (no processing) ====================
        if simple_resize_only:
            if resize_to_width is not None:
                orig_w, orig_h = pil_image.size
                new_h = int(orig_h * resize_to_width / orig_w)
                resized = pil_image.resize((resize_to_width, new_h), Image.Resampling.LANCZOS)
                self.logger.info(
                    f"Simple resize: {orig_w}×{orig_h} → {resize_to_width}×{new_h} "
                    f"(no denoising/contrast/brightness)"
                )
                if save_to_temp:
                    if not source_filename:
                        raise ValueError(
                            "original_filename required when save_to_temp=True and image is PIL/array"
                        )
                    return self._save_to_temp_dir(resized, source_filename)
                return resized
            else:
                self.logger.info("Simple resize requested but resize_to_width is None — returning as-is")
                return pil_image

        # ==================== STEP 3: ADAPTIVE RESOLUTION SCALING ====================
        t_scale_start = time.time()
        scaled_pil_image = self._adaptive_scale(pil_image, current_dpi, scale_factor=scale_factor)
        scale_time = time.time() - t_scale_start

        self.logger.debug(
            f"Adaptive scaling: {pil_image.size} → {scaled_pil_image.size} "
            f"in {scale_time:.3f}s"
        )

        # ==================== STEP 4: CONVERT TO OPENCV (BGR) FOR PROCESSING ====================
        image_cv = cv2.cvtColor(np.array(scaled_pil_image), cv2.COLOR_RGB2BGR)

        # ==================== STEP 5: ADAPTIVE DENOISE (JPEG-AWARE) ====================
        t_denoise_start = time.time()
        denoised = self._denoise_adaptive(image_cv)
        denoise_time = time.time() - t_denoise_start
        self.logger.debug(f"Denoising completed in {denoise_time:.3f}s")

        # ==================== STEP 6: ADAPTIVE CONTRAST ENHANCEMENT (JPEG-AWARE) ====================
        t_clahe_start = time.time()
        enhanced = self._enhance_contrast_adaptive(denoised)
        clahe_time = time.time() - t_clahe_start
        self.logger.debug(f"Contrast enhancement completed in {clahe_time:.3f}s")

        # ==================== STEP 7: BRIGHTNESS NORMALIZATION ====================
        t_norm_start = time.time()
        normalized = self._normalize_brightness(enhanced)
        norm_time = time.time() - t_norm_start
        self.logger.debug(f"Brightness normalization completed in {norm_time:.3f}s")

        # ==================== STEP 8: CONVERT BACK TO PIL ====================
        result_pil = Image.fromarray(cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB), mode="RGB")

        # ==================== STEP 9: FINAL RESIZE FOR MODEL INPUT ====================
        if resize_to_width is not None:
            t_resize_start = time.time()
            if save_to_temp:
                # Save to temp dir with original filename
                if not source_filename:
                    raise ValueError(
                        "original_filename required when save_to_temp=True and image is PIL/array"
                    )
                final_result = self._resize_for_model(
                    result_pil,
                    resize_to_width,
                    original_filename=source_filename
                )
            else:
                # Return PIL Image in memory
                final_result = self._resize_for_model(
                    result_pil,
                    resize_to_width,
                    original_filename=None
                )
            resize_time = time.time() - t_resize_start

            if isinstance(final_result, str):
                final_image_size = Image.open(final_result).size
            else:
                final_image_size = final_result.size

            self.logger.debug(
                f"Final resize to width={resize_to_width}: {result_pil.size} → {final_image_size} "
                f"in {resize_time:.3f}s"
            )
        else:
            final_result = result_pil
            final_image_size = result_pil.size
            resize_time = 0

        total_time = time.time() - t_total_start
        self.logger.info(
            f"✅ Preprocessing complete: {pil_image.size} → {final_image_size} "
            f"({final_image_size[0] * final_image_size[1]:,} pixels) "
            f"[load:{load_time:.3f}s, scale:{scale_time:.3f}s, denoise:{denoise_time:.3f}s, "
            f"enhance:{clahe_time:.3f}s, norm:{norm_time:.3f}s, resize:{resize_time:.3f}s] "
            f"total:{total_time:.3f}s"
        )

        return final_result

    def preprocess_and_save(
            self,
            image: Union[Image.Image, str, np.ndarray],
            output_path: Union[str, Path],
            current_dpi: int = 300,
            resize_to_width: Optional[int] = 1200,
            scale_factor: Optional[float] = None
    ) -> str:
        """
        Preprocess image and save to disk.

        Args:
            image: PIL Image, file path (str), or numpy array
            output_path: Where to save the preprocessed image
            current_dpi: Current DPI of the image (default: 300)
            resize_to_width: Final resize width (default: 1200)
            scale_factor: Pre-specified scale factor for adaptive resolution scaling,
                         bypassing the pixel-range auto-calculation

        Returns:
            Path to saved preprocessed image (str)
        """
        processed_image = self.preprocess(
            image=image,
            current_dpi=current_dpi,
            resize_to_width=resize_to_width,
            scale_factor=scale_factor
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Preserve DPI if available
        dpi = (150, 150)  # Default DPI
        if isinstance(image, Image.Image):
            dpi = image.info.get('dpi', (150, 150))

        processed_image.save(str(output_path), "PNG", dpi=dpi)

        self.logger.info(f"Saved preprocessed image to {output_path}")

        return str(output_path)

    # ==================== PRIVATE METHODS ====================

    def _detect_jpeg_format(self, image: Union[str, Path, Image.Image, np.ndarray]) -> bool:
        """
        Detect if input image is JPEG format.

        Args:
            image: Image source to check

        Returns:
            True if JPEG, False otherwise
        """
        if isinstance(image, (str, Path)):
            ext = Path(image).suffix.lower()
            return ext in ['.jpg', '.jpeg']
        elif isinstance(image, Image.Image):
            return image.format and image.format.upper() in ['JPEG', 'JPG']
        return False

    def _adaptive_scale(
            self,
            image: Image.Image,
            current_dpi: int,
            scale_factor: Optional[float] = None
    ) -> Image.Image:
        """
        Adaptively scale image based on profile target pixel range.

        Target: ~600k-1.2M pixels, DPI held near profile.target_dpi (240 for HANDWRITTEN)

        Args:
            image: PIL Image
            current_dpi: Current DPI
            scale_factor: Pre-specified scale factor to apply directly, bypassing the
                          pixel-range auto-calculation. Use when the caller already knows
                          the factor needed to bring the image to the target DPI.

        Returns:
            Scaled PIL Image
        """
        width, height = image.size
        current_pixels = width * height
        target_dpi = self.profile.target_dpi

        if scale_factor is None:
            target_min_pixels = self.profile.target_min_pixels  # 600k
            target_max_pixels = self.profile.target_max_pixels  # 1.2M

            # Calculate scale factor
            if current_pixels < target_min_pixels:
                scale_factor = (target_min_pixels / current_pixels) ** 0.5
            elif current_pixels > target_max_pixels:
                scale_factor = (target_max_pixels / current_pixels) ** 0.5
            else:
                scale_factor = 1.0
        else:
            self.logger.debug(f"Using pre-specified scale factor: {scale_factor:.3f}")

        if abs(scale_factor - 1.0) < 0.01:  # No scaling needed
            return image

        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        effective_dpi = current_dpi * scale_factor

        self.logger.debug(
            f"Adaptive scale: {current_pixels:,} pixels → {new_width * new_height:,} "
            f"(factor: {scale_factor:.2f}, effective DPI: {effective_dpi:.0f}, "
            f"target DPI: {target_dpi})"
        )

        return image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

    def _denoise_adaptive(self, image_cv: np.ndarray) -> np.ndarray:
        """
        Adaptive denoising based on image format (JPEG vs PNG).

        JPEG: Lighter denoising (h reduced by 30%) to avoid over-smoothing
        PNG: Standard denoising (h as specified in profile)

        Args:
            image_cv: OpenCV/numpy image array (BGR format)

        Returns:
            Denoised image array
        """
        if not self.profile.denoise:
            self.logger.debug("Denoising disabled")
            return image_cv

        self.logger.debug("Starting adaptive denoising...")
        start_time = time.time()

        try:
            # Adjust h parameter for JPEG to prevent over-smoothing
            h = self.profile.denoise_h
            if self._is_jpeg:
                # Reduce denoise strength for JPEG (30% reduction)
                h = max(4, int(h * 0.7))
                self.logger.debug(
                    f"JPEG detected - reducing denoise h from {self.profile.denoise_h} to {h}"
                )

            template_window = self.profile.denoise_template_window
            search_window = self.profile.denoise_search_window

            # Use positional arguments to avoid keyword argument issues
            denoised = cv2.fastNlMeansDenoisingColored(
                image_cv,
                None,  # dst (output image, can be None)
                h,  # h parameter (strength of filter)
                h,  # hForColorComponents (use same as h)
                template_window,  # templateWindowSize
                search_window  # searchWindowSize
            )

            elapsed = time.time() - start_time
            self.logger.debug(f"Denoising completed in {elapsed:.3f}s")

            return denoised

        except TypeError as e:
            # Fallback: try without hForColorComponents (older or different OpenCV builds)
            self.logger.warning(f"fastNlMeansDenoisingColored failed with keyword args: {e}")
            self.logger.info("Retrying with positional args only...")

            try:
                h = self.profile.denoise_h
                if self._is_jpeg:
                    h = max(4, int(h * 0.7))

                denoised = cv2.fastNlMeansDenoisingColored(
                    image_cv,
                    None,
                    h,
                    self.profile.denoise_template_window,
                    self.profile.denoise_search_window
                )
                self.logger.debug("Denoising succeeded with fallback signature")
                return denoised
            except Exception as fallback_error:
                self.logger.warning(f"Denoising failed completely: {fallback_error}. Skipping denoising.")
                return image_cv

        except cv2.error as e:
            self.logger.warning(f"OpenCV error during denoising: {e}. Skipping denoising.")
            return image_cv

    def _enhance_contrast_adaptive(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Adaptive CLAHE contrast enhancement based on image format.

        JPEG: Lower clip limit (reduced by 40%) to avoid artifacts
        PNG: Standard clip limit from profile

        Uses LAB color space (better for medical documents than HSV).

        Args:
            image_bgr: OpenCV BGR image

        Returns:
            Contrast-enhanced image
        """
        if not self.profile.enhance_contrast:
            self.logger.debug("Contrast enhancement disabled")
            return image_bgr

        self.logger.debug("Starting adaptive contrast enhancement...")
        start_time = time.time()

        try:
            clip_limit = self.profile.clahe_clip_limit
            if self._is_jpeg:
                # Reduce CLAHE clip limit for JPEG (40% reduction)
                clip_limit = max(1.0, clip_limit * 0.6)
                self.logger.debug(
                    f"JPEG detected - reducing CLAHE clip limit from {self.profile.clahe_clip_limit:.1f} to {clip_limit:.1f}"
                )

            tile_grid_size = self.profile.clahe_tile_grid_size  # (8, 8) typical

            # Convert to LAB (better for medical documents than HSV)
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]

            # Apply CLAHE to L channel only
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            l_enhanced = clahe.apply(l_channel)

            # Merge back
            lab[:, :, 0] = l_enhanced
            enhanced_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            elapsed = time.time() - start_time
            self.logger.debug(
                f"Contrast enhancement completed in {elapsed:.3f}s "
                f"(clip_limit={clip_limit:.1f}, tile_grid={tile_grid_size})"
            )

            return enhanced_bgr

        except Exception as e:
            self.logger.warning(f"Contrast enhancement failed: {e}. Skipping.")
            return image_bgr

    def _normalize_brightness(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Normalize brightness using percentile-based approach.

        Args:
            image_bgr: OpenCV BGR image

        Returns:
            Brightness-normalized image
        """
        lower_percentile = self.profile.brightness_percentile_lower
        upper_percentile = self.profile.brightness_percentile_upper

        # Convert to grayscale for percentile calculation
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # Calculate percentiles
        lower_val = np.percentile(gray, lower_percentile)
        upper_val = np.percentile(gray, upper_percentile)

        # Avoid division by zero
        if upper_val - lower_val < 1:
            self.logger.debug("Brightness normalization skipped (low contrast)")
            return image_bgr

        # Normalize each channel
        normalized_bgr = image_bgr.copy().astype(np.float32)
        for c in range(3):
            normalized_bgr[:, :, c] = np.clip(
                (normalized_bgr[:, :, c] - lower_val) / (upper_val - lower_val) * 255,
                0,
                255
            )

        self.logger.debug(
            f"Brightness normalized (lower_percentile={lower_percentile}, "
            f"upper_percentile={upper_percentile}, range=[{lower_val:.1f}, {upper_val:.1f}])"
        )

        return normalized_bgr.astype(np.uint8)

    def _resize_for_model(
            self,
            image: Image.Image,
            max_width: int = 1200,
            original_filename: Optional[str] = None
    ) -> Union[Image.Image, str]:
        """
        Final resize for model input.

        Scales image to max_width while maintaining aspect ratio.
        Can optionally save to temp directory with original filename.

        Args:
            image: PIL Image
            max_width: Target maximum width (default: 1200)
            original_filename: If provided, saves to temp dir and returns file path.
                              If None, returns PIL Image.

        Returns:
            PIL Image (if original_filename is None) or str path (if original_filename provided)
        """
        width, height = image.size

        if width <= max_width:
            self.logger.debug(f"Image already within max_width ({width} ≤ {max_width})")
            if original_filename:
                # Save with original filename to temp dir
                return self._save_to_temp_dir(image, original_filename)
            return image

        # Calculate new height maintaining aspect ratio
        ratio = max_width / width
        new_height = int(height * ratio)

        resized = image.resize(
            (max_width, new_height),
            Image.Resampling.LANCZOS
        )

        self.logger.debug(
            f"Final resize: {width}×{height} → {max_width}×{new_height}"
        )

        if original_filename:
            # Save with original filename to temp dir
            return self._save_to_temp_dir(resized, original_filename)

        return resized

    def _save_to_temp_dir(
            self,
            image: Image.Image,
            filename: str
    ) -> str:
        """
        Save image to temp directory with original filename.

        Args:
            image: PIL Image to save
            filename: Original filename to use

        Returns:
            Full path to saved image as string
        """
        try:
            temp_dir = Path(settings.UPLOAD_TEMP_DIR)
        except (AttributeError, Exception) as e:
            self.logger.warning(f"Could not load settings.UPLOAD_TEMP_DIR: {e}. Using fallback.")
            temp_dir = Path("./uploads/temp")

        temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = temp_dir / filename

        # Preserve DPI if available
        dpi = image.info.get('dpi', (150, 150))

        image.save(str(output_path), "PNG", dpi=dpi)

        self.logger.debug(f"Saved resized image to temp dir: {output_path}")

        return str(output_path)


# ==================== CONVENIENCE FUNCTION ====================

def preprocess_image(
        image: Union[Image.Image, str, np.ndarray],
        profile: Optional[PreprocessingProfile] = None,
        current_dpi: int = 300,
        resize_to_width: Optional[int] = 1200
) -> Image.Image:
    """
    Convenience function for one-off preprocessing.

    Uses HANDWRITTEN profile by default (preserves fine details).

    Args:
        image: PIL Image, file path, or numpy array
        profile: PreprocessingProfile (defaults to HANDWRITTEN if None)
        current_dpi: Current DPI (default: 300)
        resize_to_width: Final resize width (default: 1200)

    Returns:
        Preprocessed PIL Image
    """
    if profile is None:
        profile_dict = get_profile("HANDWRITTEN")
        # Convert dict to dataclass
        profile = PreprocessingProfile(
            name="HANDWRITTEN",
            max_pixels=profile_dict.get("max_pixels", 1_800_000),
            target_dpi=profile_dict.get("target_dpi", 240),
            denoise=profile_dict.get("denoise", True),
            denoise_h=profile_dict.get("denoise_h", 6),
            enhance_contrast=profile_dict.get("enhance_contrast", True),
            clahe_clip_limit=profile_dict.get("clahe_clip_limit", 1.8),
        )

    preprocessor = AdaptivePreprocessor(profile=profile)
    return preprocessor.preprocess(
        image=image,
        current_dpi=current_dpi,
        resize_to_width=resize_to_width
    )
