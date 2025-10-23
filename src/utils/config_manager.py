"""
Configuration Manager
Handles loading and validating configuration files
"""

import json
import os
import logging
from pathlib import Path


class ConfigManager:
    """Configuration file manager"""

    def __init__(self, config_path='config.json'):
        """
        Initialize configuration manager

        Args:
            config_path: Path to configuration file
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        """
        Load configuration from JSON file

        Returns:
            dict: Configuration dictionary
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_path}")
                return self._validate_config(config)

        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def _validate_config(self, config):
        """
        Validate and fill in default values

        Args:
            config: Configuration dictionary

        Returns:
            dict: Validated configuration
        """
        # Define required keys
        required_keys = {
            'spotify': ['client_id', 'client_secret', 'redirect_uri'],
            'display': ['rows', 'cols', 'brightness']
        }

        # Check required keys
        for section, keys in required_keys.items():
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

            for key in keys:
                if key not in config[section]:
                    raise ValueError(f"Missing required configuration key: {section}.{key}")

        # Set defaults for optional values
        config.setdefault('modes', {})
        config['modes'].setdefault('default', 'music')
        config['modes'].setdefault('auto_switch', True)

        config.setdefault('web_server', {})
        config['web_server'].setdefault('enabled', True)
        config['web_server'].setdefault('host', '0.0.0.0')
        config['web_server'].setdefault('port', 5000)

        config.setdefault('weather', {})
        config['weather'].setdefault('enabled', False)

        config.setdefault('sports', {})
        config['sports'].setdefault('enabled', False)

        config.setdefault('logging', {})
        config['logging'].setdefault('level', 'INFO')

        return config

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
                self.logger.info(f"Configuration saved to {self.config_path}")
                return True

        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    def get(self, key_path, default=None):
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated key path (e.g., 'spotify.client_id')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path, value):
        """
        Set configuration value using dot notation

        Args:
            key_path: Dot-separated key path
            value: Value to set
        """
        keys = key_path.split('.')
        config = self.config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value
