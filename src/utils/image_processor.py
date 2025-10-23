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

        # Initialize image cache
        self.image_cache = LRUCache(maxsize=50) if self.cache_enabled else None

        # Create cache directory
        self.cache_dir = Path.home() / '.cache' / 'spotify-display' / 'images'
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_image(self, url):
        """
        Download image from URL

        Args:
            url: Image URL

        Returns:
            PIL.Image: Downloaded image
        """
        try:
            # Check memory cache first
            if self.cache_enabled and url in self.image_cache:
                self.logger.debug(f"Image loaded from memory cache: {url}")
                return self.image_cache[url]

            # Check disk cache
            cache_filename = self._get_cache_filename(url)
            cache_path = self.cache_dir / cache_filename

            if self.cache_enabled and cache_path.exists():
                self.logger.debug(f"Image loaded from disk cache: {cache_filename}")
                image = Image.open(cache_path)
                self.image_cache[url] = image
                return image

            # Download image
            self.logger.debug(f"Downloading image: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))

            # Cache the image
            if self.cache_enabled:
                image.save(cache_path)
                self.image_cache[url] = image

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
        try:
            # Download if URL
            if isinstance(image_or_url, str):
                image = self.download_image(image_or_url)
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

            return image

        except Exception as e:
            self.logger.error(f"Error processing album art: {e}")
            return self.create_placeholder_image(size, "Error")

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
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
            draw.text(position, text, font=font, fill=color)
        except Exception as e:
            self.logger.error(f"Error creating text image: {e}")

        return image

    def _get_cache_filename(self, url):
        """
        Generate cache filename from URL

        Args:
            url: Image URL

        Returns:
            str: Cache filename
        """
        # Create hash of URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return f"{url_hash}.png"

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
