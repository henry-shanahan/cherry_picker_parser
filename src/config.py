#!/usr/bin/env python3
"""
Configuration management for shipping data parser.
"""

import os
from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class AppConfig:
    """Application configuration settings."""

    # File settings
    output_filename: str = "parsed_shipping_data.xlsx"
    default_year: int = datetime.now().year

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Parser settings
    enable_typo_correction: bool = True
    enable_freight_calculation: bool = True

    # CLI settings
    stdin_prompt_message: str = (
            "📋 Please paste your unstructured shipping data below.\n"
            "   Press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows) to finish.\n"
            + "-" * 60
    )

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create configuration from environment variables."""
        return cls(
            output_filename=os.getenv('SHIPPING_OUTPUT_FILE', cls.output_filename),
            default_year=int(os.getenv('SHIPPING_DEFAULT_YEAR', str(cls.default_year))),
            log_level=os.getenv('SHIPPING_LOG_LEVEL', cls.log_level),
            enable_typo_correction=os.getenv('SHIPPING_ENABLE_TYPO_CORRECTION', 'true').lower() == 'true',
            enable_freight_calculation=os.getenv('SHIPPING_ENABLE_FREIGHT_CALC', 'true').lower() == 'true',
        )

    def validate(self) -> None:
        """Validate configuration settings."""
        if self.default_year < 2000 or self.default_year > 2100:
            raise ValueError(f"Invalid default year: {self.default_year}")

        valid_log_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")

        if not self.output_filename.endswith(('.xlsx', '.xls')):
            raise ValueError(f"Output filename must end with .xlsx or .xls: {self.output_filename}")


@dataclass
class ParserConfig:
    """Configuration specific to the shipping data parser."""

    # Known charterers for recognition
    charterers: List[str] = None

    # Cargo type patterns for recognition
    cargo_patterns: List[str] = None

    # Month abbreviations
    month_names: List[str] = None

    def __post_init__(self):
        """Initialize default values after creation."""
        if self.charterers is None:
            self.charterers = [
                "P66", "Neste", "Bunge", "Cargill", "Nova", "Olam", "ENI", "DGD",
                "SK Energy", "ICOF", "Kolmar", "Petroineos", "Wilmar", "GAM", "Aramco",
                "First Resources", "Alpha star", "St, Bernards Resources", "Mewah",
                "EFK", "Sime Darby", "Xiamen ITG", "Glencore", "SA Services", "CNR"
            ]

        if self.cargo_patterns is None:
            self.cargo_patterns = [
                r'UCO\s*\+\s*Tallow', r'UCO/UCOME/Bio\s+feedstock', r'UCO/Bio\s+feedstocks?',
                r'POME/Palms/UCO', r'Palm/POME/EFBO/SBEO', r'SAF/UCO/FAME', r'Fishoil\s+and\s+UCO',
                r'Palm\s+oil\s+products', r'Palm\s+oil', r'Palmoil', r'Palms',
                r'POP', r'BIOS', r'Fishoil', r'UCO', r'UCOME', r'Tallow', r'Benzene',
                r'MTBE', r'POME', r'FAME', r'EFBO', r'SBEO', r'SAF', r'Bio\s+feedstocks?',
                # New cargo types
                r'RPKO', r'S\.Acid', r'Chems', r'Biofeedstocks/chems'
            ]

        if self.month_names is None:
            self.month_names = [
                'jan', 'feb', 'mar', 'apr', 'may', 'jun',
                'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
            ]

    def add_charterer(self, charterer: str) -> None:
        """Add a new charterer to the recognition list."""
        if charterer not in self.charterers:
            self.charterers.append(charterer)

    def add_cargo_pattern(self, pattern: str) -> None:
        """Add a new cargo pattern for recognition."""
        if pattern not in self.cargo_patterns:
            self.cargo_patterns.append(pattern)