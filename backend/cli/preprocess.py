# backend/cli/preprocess.py

import click
import logging
from typing import Optional
from pathlib import Path
from PIL import Image

from config.preprocessing_profiles import get_profile, PreprocessingProfile
from services.preprocessing import AdaptivePreprocessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--file-path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Single file to process",
    default=None,
)
@click.option(
    "--form-type",
    type=click.Choice(["COMPLEX_FORM", "SIMPLE_TEXT", "HANDWRITTEN"], case_sensitive=False),
    help="Form type for preprocessing profile",
    default="HANDWRITTEN",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory for processed images",
    default="./output",
)
@click.option(
    "--current-dpi",
    type=int,
    help="Current DPI of input image",
    default=300,
)
@click.option(
    "--resize-width",
    type=int,
    help="Final resize width for model input (None to skip)",
    default=1200,
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable debug logging",
)
def preprocess(
        file_path: Optional[str],
        form_type: str,
        output_dir: str,
        current_dpi: int,
        resize_width: Optional[int],
        verbose: bool,
) -> None:
    """
    CLI tool for preprocessing medical form images.

    Examples:
        # Process single file with ITF profile
        python -m cli.preprocess --file-path input.png --form-type ITF

        # Process with custom output directory
        python -m cli.preprocess --file-path form.jpg --output-dir ./processed

        # Skip final resize
        python -m cli.preprocess --file-path image.png --resize-width None

        # Enable debug logging
        python -m cli.preprocess --file-path image.png --verbose
    """

    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    if not file_path:
        click.echo("❌ Error: --file-path is required", err=True)
        raise click.Exit(1)

    file_path_obj = Path(file_path)
    output_dir_obj = Path(output_dir)
    output_dir_obj.mkdir(parents=True, exist_ok=True)

    try:
        # ==================== LOAD PROFILE ====================
        logger.info(f"Loading preprocessing profile: {form_type}")
        profile_dict = get_profile(form_type)

        # Convert dict to PreprocessingProfile dataclass
        profile = _dict_to_profile(profile_dict, name=form_type)
        logger.info(f"✅ Profile loaded: {profile.name}")
        logger.debug(f"   max_pixels={profile.max_pixels}, target_dpi={profile.target_dpi}")
        logger.debug(f"   denoise={profile.denoise}, enhance_contrast={profile.enhance_contrast}")
        logger.debug(f"   clahe_clip_limit={profile.clahe_clip_limit}")

        # ==================== INITIALIZE PREPROCESSOR ====================
        logger.info("Initializing AdaptivePreprocessor...")
        preprocessor = AdaptivePreprocessor(profile=profile)

        # ==================== PREPROCESS IMAGE ====================
        logger.info(f"Processing: {file_path_obj.name}")
        logger.info(f"  Input DPI: {current_dpi}")
        logger.info(f"  Output resize width: {resize_width if resize_width else 'None (skip)'}")

        processed_image = preprocessor.preprocess(
            image=str(file_path_obj),
            current_dpi=current_dpi,
            resize_to_width=resize_width,
            save_to_temp=False
        )

        # ==================== SAVE OUTPUT ====================
        output_filename = file_path_obj.stem + ".png"
        output_path = output_dir_obj / output_filename

        if isinstance(processed_image, str):
            # Already saved to temp dir
            logger.info(f"✅ Image already saved to temp dir: {processed_image}")
            output_path = processed_image
        else:
            # Save PIL Image
            dpi = (150, 150)
            try:
                original_image = Image.open(str(file_path_obj))
                dpi = original_image.info.get('dpi', (150, 150))
            except Exception as e:
                logger.warning(f"Could not extract DPI from original: {e}")

            processed_image.save(str(output_path), "PNG", dpi=dpi)
            logger.info(f"✅ Preprocessed image saved: {output_path}")

        # ==================== SUMMARY ====================
        logger.info("\n" + "=" * 60)
        logger.info("📊 PREPROCESSING SUMMARY")
        logger.info("=" * 60)

        original_image = Image.open(str(file_path_obj))
        orig_size = original_image.size
        orig_pixels = orig_size[0] * orig_size[1]

        if isinstance(processed_image, str):
            processed_img = Image.open(processed_image)
        else:
            processed_img = processed_image

        proc_size = processed_img.size
        proc_pixels = proc_size[0] * proc_size[1]

        logger.info(f"Original:    {orig_size[0]}×{orig_size[1]} ({orig_pixels:,} pixels)")
        logger.info(f"Processed:   {proc_size[0]}×{proc_size[1]} ({proc_pixels:,} pixels)")
        logger.info(f"Compression: {(1 - proc_pixels / orig_pixels) * 100:.1f}%")
        logger.info(f"Output:      {output_path}")
        logger.info("=" * 60 + "\n")

        click.echo(f"✅ Successfully processed: {file_path_obj.name}")

    except FileNotFoundError as e:
        click.echo(f"❌ File not found: {e}", err=True)
        raise click.Exit(1)
    except TypeError as e:
        click.echo(f"❌ Type error: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Exit(1)


def _dict_to_profile(profile_dict: dict, name: str = "") -> PreprocessingProfile:
    """
    Convert dictionary profile to PreprocessingProfile dataclass.

    Provides sensible defaults for missing extended attributes.

    Args:
        profile_dict: Dictionary with profile settings
        name: Profile name

    Returns:
        PreprocessingProfile instance
    """
    return PreprocessingProfile(
        name=name,
        max_pixels=profile_dict.get("max_pixels", 1_500_000),
        min_dpi=profile_dict.get("min_dpi", 150),
        target_dpi=profile_dict.get("target_dpi", 200),
        denoise=profile_dict.get("denoise", True),
        enhance_contrast=profile_dict.get("enhance_contrast", True),
        clahe_clip_limit=profile_dict.get("clahe_clip_limit", 2.5),
        target_min_pixels=profile_dict.get("target_min_pixels", 600_000),
        target_max_pixels=profile_dict.get("target_max_pixels", 1_200_000),
        denoise_h=profile_dict.get("denoise_h", 10),
        denoise_template_window=profile_dict.get("denoise_template_window", 7),
        denoise_search_window=profile_dict.get("denoise_search_window", 21),
        clahe_tile_grid_size=profile_dict.get("clahe_tile_grid_size", (8, 8)),
        brightness_percentile_lower=profile_dict.get("brightness_percentile_lower", 2),
        brightness_percentile_upper=profile_dict.get("brightness_percentile_upper", 98),
    )


if __name__ == "__main__":
    preprocess()
