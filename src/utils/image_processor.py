"""
Image Processor
Handles image download, processing, and optimization for LED display
"""

import os
import logging
import hashlib
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from cachetools import LRUCache

from utils.runtime import cache_dir


class ImageProcessor:
    """Process and optimize images for LED matrix display"""

    def __init__(self, config=None):
        """
        Initialize image processor

        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.cache_enabled = self.config.get('cache_images', True)
        self.cache_size = self.config.get('cache_size_mb', 100)

        # Caches hold the *processed* display-sized image (64x64 is ~12 KB),
        # not the 640px original: the old full-size cache cost ~1.2 MB of RAM
        # per entry (up to ~58 MB) and ~220 KB of SD card per track, unbounded.
        self.image_cache = LRUCache(maxsize=200) if self.cache_enabled else None

        # Create cache directory
        self.cache_dir = cache_dir() / 'images'
        if self.cache_enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.logger.warning(f"Image disk cache disabled: {e}")

    def download_image(self, url, target_size=None):
        """
        Download an image from a URL (uncached).

        Args:
            url: Image URL
            target_size: Optional (w, h). For JPEGs this lets the decoder
                downscale while decoding (DCT scaling), which is several times
                faster than decoding at full size and resizing afterwards.

        Returns:
            PIL.Image or None
        """
        try:
            self.logger.debug(f"Downloading image: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            if target_size:
                # Decode at >= 2x the target so the LANCZOS resize still has
                # detail to work with. No-op for non-JPEG images.
                image.draft('RGB', (target_size[0] * 2, target_size[1] * 2))
            image.load()
            return image
        except Exception as e:
            self.logger.error(f"Error downloading image from {url}: {e}")
            return None

    def process_album_art(self, image_or_url, size=(64, 64)):
        """
        Process album art for LED display

        Args:
            image_or_url: PIL Image or URL string
            size: Target size tuple (width, height)

        Returns:
            PIL.Image: Processed image ready for display
        """
        size = tuple(size)
        cache_key = None
        try:
            # Download if URL (checking the processed-image caches first)
            if isinstance(image_or_url, str):
                cache_key = self._cache_key(image_or_url, size)
                cached = self._cache_get(cache_key)
                if cached is not None:
                    return cached
                image = self.download_image(image_or_url, target_size=size)
                if image is None:
                    return self.create_placeholder_image(size, "No Album Art")
            else:
                image = image_or_url

            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Center crop to square
            image = self._center_crop_square(image)

            # Resize to target size
            image = image.resize(size, Image.LANCZOS)

            # Enhance for LED display
            image = self._enhance_for_led(image)

            if cache_key:
                self._cache_put(cache_key, image)

            return image

        except Exception as e:
            self.logger.error(f"Error processing album art: {e}")
            return self.create_placeholder_image(size, "Error")

    # ------------------------------------------------------------- caching

    def _cache_key(self, url, size):
        """Key covers everything that changes the output, so tweaking contrast
        etc. in the admin panel doesn't serve stale cached art."""
        settings = (
            size,
            self.config.get('enhance_contrast', True), self.config.get('contrast_factor', 1.2),
            self.config.get('enhance_saturation', True), self.config.get('saturation_factor', 1.1),
        )
        return hashlib.md5(f"{url}|{settings}".encode()).hexdigest()

    def _cache_get(self, key):
        if not self.cache_enabled:
            return None
        image = self.image_cache.get(key)
        if image is not None:
            return image
        path = self.cache_dir / f"{key}.png"
        try:
            with Image.open(path) as cached:
                image = cached.convert('RGB')
            os.utime(path)  # mark as recently used for pruning
            self.image_cache[key] = image
            self.logger.debug(f"Album art loaded from disk cache: {path.name}")
            return image
        except (OSError, ValueError):
            return None

    def _cache_put(self, key, image):
        if not self.cache_enabled:
            return
        self.image_cache[key] = image
        try:
            image.save(self.cache_dir / f"{key}.png")
            self._prune_disk_cache()
        except OSError as e:
            self.logger.debug(f"Could not write image cache: {e}")

    def _prune_disk_cache(self):
        """Keep the disk cache under cache_size_mb, dropping least recently used."""
        limit = max(1, int(self.cache_size)) * 1024 * 1024
        try:
            files = [(f, f.stat()) for f in self.cache_dir.glob('*.png')]
        except OSError:
            return
        total = sum(st.st_size for _, st in files)
        if total <= limit:
            return
        for f, st in sorted(files, key=lambda item: item[1].st_mtime):
            try:
                f.unlink()
                total -= st.st_size
            except OSError:
                pass
            if total <= limit * 0.9:
                break

    def _center_crop_square(self, image):
        """
        Crop image to square from center

        Args:
            image: PIL Image

        Returns:
            PIL.Image: Square cropped image
        """
        width, height = image.size
        min_dim = min(width, height)

        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim

        return image.crop((left, top, right, bottom))

    def _enhance_for_led(self, image):
        """
        Enhance image for better LED display

        Args:
            image: PIL Image

        Returns:
            PIL.Image: Enhanced image
        """
        # Enhance contrast
        if self.config.get('enhance_contrast', True):
            contrast_factor = self.config.get('contrast_factor', 1.2)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(contrast_factor)

        # Enhance saturation
        if self.config.get('enhance_saturation', True):
            saturation_factor = self.config.get('saturation_factor', 1.1)
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(saturation_factor)

        return image

    def create_placeholder_image(self, size, text=""):
        """
        Create a placeholder image

        Args:
            size: Image size tuple
            text: Text to display

        Returns:
            PIL.Image: Placeholder image
        """
        image = Image.new('RGB', size, color=(20, 20, 20))
        draw = ImageDraw.Draw(image)

        if text:
            # Try to center text
            try:
                font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
                draw.text(position, text, font=font, fill=(100, 100, 100))
            except:
                pass

        return image

    def create_text_image(self, text, size, font_size=8, color=(255, 255, 255), bg_color=(0, 0, 0)):
        """
        Create an image with text

        Args:
            text: Text to render
            size: Image size tuple
            font_size: Font size
            color: Text color
            bg_color: Background color

        Returns:
            PIL.Image: Text image
        """
        image = Image.new('RGB', size, color=bg_color)
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.load_default()
            bbox = draw.multiline_textbbox((0, 0), text, font=font, align='center')
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((size[0] - text_width) // 2 - bbox[0], (size[1] - text_height) // 2 - bbox[1])
            draw.multiline_text(position, text, font=font, fill=color, align='center')
        except Exception as e:
            self.logger.error(f"Error creating text image: {e}")

        return image

    def clear_cache(self):
        """Clear image cache"""
        if self.image_cache:
            self.image_cache.clear()

        if self.cache_dir.exists():
            for file in self.cache_dir.glob('*.png'):
                try:
                    file.unlink()
                except Exception as e:
                    self.logger.error(f"Error deleting cache file {file}: {e}")

        self.logger.info("Image cache cleared")
