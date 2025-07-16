#!/usr/bin/env python3
"""
Core shipping data parser implementation.
"""

import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging

from models import ShippingRecord
from config import AppConfig, ParserConfig

logger = logging.getLogger(__name__)


class ShippingDataParser:
    """Main parser for converting unstructured shipping data into structured records."""

    def __init__(self, app_config: AppConfig = None, parser_config: ParserConfig = None):
        """Initialize parser with configuration."""
        self.app_config = app_config or AppConfig()
        self.parser_config = parser_config or ParserConfig()

        # Create month lookup dictionary
        self.months = {
            month: idx + 1 for idx, month in enumerate(self.parser_config.month_names)
        }

    def parse_shipping_data(self, text_data: str) -> List[Dict]:
        """Parse shipping data text into structured records."""
        if not text_data or not text_data.strip():
            logger.warning("Empty input data provided")
            return []

        records = []
        lines = text_data.strip().split('\n')
        failed_count = 0

        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = self._parse_line(line)
                if record:
                    self._finalize_record(record)
                    records.append(record.to_dict())
                else:
                    logger.warning(f"Line {line_number}: No record created")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Line {line_number}: Failed to parse - {e}")
                failed_count += 1
                continue

        success_count = len(records)
        total_lines = len([l for l in lines if l.strip()])

        logger.info(f"Parsed {success_count} records from {total_lines} lines "
                    f"({failed_count} failed)")

        return records

    def _parse_line(self, line: str) -> Optional[ShippingRecord]:
        """Parse a single line of shipping data."""
        if self._is_charterer_led_format(line):
            return self._parse_charterer_format(line)
        else:
            return self._parse_standard_format(line)

    def _is_charterer_led_format(self, line: str) -> bool:
        """Check if line follows charterer-led format (e.g., 'P66 / Vessel / Cargo')."""
        return any(line.startswith(f"{charterer} /")
                   for charterer in self.parser_config.charterers)

    def _parse_charterer_format(self, line: str) -> ShippingRecord:
        """Parse charterer-led format: 'P66 / Vessel / Cargo / Ports / Dates / Freight'."""
        record = ShippingRecord()
        parts = [p.strip() for p in line.split('/')]

        if len(parts) > 0:
            record.charterer = parts[0]
        if len(parts) > 1:
            record.vessel_name = parts[1]
        if len(parts) > 2:
            self._extract_quantity_cargo_from_string(parts[2], record)
        if len(parts) > 3:
            self._extract_ports_from_string(parts[3], record)
        if len(parts) > 4:
            remaining = ' / '.join(parts[4:])
            self._extract_laycan_and_freight(remaining, record)

        return record

    def _parse_standard_format(self, line: str) -> ShippingRecord:
        """Parse standard format: 'Vessel Quantity Cargo Ports Dates Freight Charterer'."""
        record = ShippingRecord()
        work_line = self._clean_line_suffixes(line)

        # Extract charterer
        work_line = self._extract_charterer(work_line, record)

        # Extract laycan and freight
        work_line = self._extract_laycan_and_freight(work_line, record)

        # Extract vessel, quantity, cargo, and ports
        self._extract_vessel_cargo_ports(work_line, record)

        return record

    def _clean_line_suffixes(self, line: str) -> str:
        """Remove common suffixes that interfere with parsing."""
        suffixes = [
            r'\s*-\s*Failed\s*$', r'\s*-\s*on\s+subs\s*$', r'\s+RNR\s*$',
            r'\s+bss\s+\w+\s*$', r'\s+\d/\d\s*$', r'\s+n\s+Trip\s+T/C.*$',
            r'\s+Trip\s+t/C.*$'
        ]
        for suffix in suffixes:
            line = re.sub(suffix, '', line, flags=re.IGNORECASE)
        return line

    def _extract_charterer(self, line: str, record: ShippingRecord) -> str:
        """Extract charterer from line and return cleaned line."""
        for charterer in self.parser_config.charterers:
            pattern = rf'\b{re.escape(charterer)}\b'
            if re.search(pattern, line, re.IGNORECASE):
                record.charterer = charterer
                line = re.sub(pattern, '', line, flags=re.IGNORECASE).strip()
                break
        return line

    def _extract_laycan_and_freight(self, text: str, record: ShippingRecord) -> str:
        """Extract laycan and freight information from text."""
        work_text = text

        # Laycan patterns - more comprehensive
        laycan_patterns = [
            r'\d{1,2}\s+\w+\s*[–-]\s*\d{1,2}\s+\w+',  # 25 Jun – 5 July
            r'\d{1,2}-\d{1,2}\s+\w+',  # 25-30 Jun, 4-10 July
            r'end\s+\w+\s*[–-]\s*ely\s+\w+',  # end June – ely July
            r'[12][Hh]\s+\w+',  # 1H July, 2H June
            r'[Ee](?:ly|arly)\s+\w+',  # Ely Jun, Early June
            r'[Ee]nd\s+\w+',  # end June
            r'mid\s+\w+',  # mid Jul
            r'\w+\s+dates',  # June dates
            r'1\s+H\s+\w+',  # 1 H Jul (with space)
            r'\d{1,2}-\d{1,2}\s+\w+(?:uary|arch|pril|une|uly|ugust|eptember|ctober|ovember|ecember)',
            # More specific month matching
        ]

        # Try to find laycan pattern
        for pattern in laycan_patterns:
            if match := re.search(pattern, work_text, re.IGNORECASE):
                record.laycan = match.group(0).strip()
                work_text = work_text.replace(match.group(0), '').strip()
                break

        # Freight patterns
        freight_patterns = [
            r'USD\s+[\d,\.]+\s*M\s+Lumpsum',  # USD 2.15M Lumpsum
            r'[YU]?[Uu]sd?\s+(?:hi|lo|mid)\s+[\d,\.]+\s*M',  # USd hi 2 M
            r'[YU]?[Uu]sd?\s+[\d,\.]+\s*M',  # Usd 2.85 M
            r'[YU]?[Uu]sd?\s+[\d,\.]+\s+pmt',  # Usd 35 pmt, YUsd 55 pmt
            r'[YU]?[Uu]sd?\s+[\d,\.]+\s*K\s+PD',  # Usd 24K PD
            r'[YU]?[Uu]sd?\s+(?:low|hi|mid|miod|hih)\s+\d+ies',  # With Usd prefix
            r'(?:low|hi|mid|miod|hih)\s+\d+ies',  # Without Usd prefix
            r'RNR'  # Rate not reported
        ]

        # Try to find freight pattern
        for pattern in freight_patterns:
            if match := re.search(pattern, work_text, re.IGNORECASE):
                record.freight = match.group(0).strip()
                work_text = work_text.replace(match.group(0), '').strip()
                break

        return work_text

    def _extract_vessel_cargo_ports(self, text: str, record: ShippingRecord):
        """Extract vessel name, quantity, cargo, and ports from text."""
        # Quantity patterns - more comprehensive to handle various formats
        qty_patterns = [
            r'(\d+-?\d*)\s*(?:ktons|ktrons|ktpns|Ktons|Mtons|MT)\b',  # With units
            r'(\d+(?:,\d{3})*)\s+(?=[A-Z][a-z])',  # Plain numbers before cargo (like "8600 Benzene")
        ]

        qty_match = None
        for pattern in qty_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                qty_match = match
                break

        if qty_match:
            # Extract vessel name (everything before quantity)
            vessel_part = text[:qty_match.start()].strip()
            vessel_part = re.sub(r'\([^)]*\)', '', vessel_part).strip()  # Remove parentheses
            if vessel_part:
                record.vessel_name = vessel_part

            # Parse quantity
            qty_str = qty_match.group(1)
            if '-' in qty_str:
                qty_str = qty_str.split('-')[0]  # Take lower bound of range
            qty_str = qty_str.replace(',', '')

            try:
                qty_value = float(qty_str)
                unit = qty_match.group(0).lower()
                # Convert to MT
                if any(x in unit for x in ['ktons', 'ktrons', 'ktpns']):  # Include ktpns typo
                    qty_value *= 1000
                record.quantity_mt = qty_value
            except ValueError:
                logger.warning(f"Could not parse quantity: {qty_str}")

            # Extract cargo and ports from remaining text
            remaining = text[qty_match.end():].strip()
            self._extract_cargo_and_ports(remaining, record)
        else:
            logger.debug(f"No quantity pattern found in: {text}")
            # If no quantity found, try to extract cargo and ports from full text
            self._extract_cargo_and_ports(text, record)

    def _extract_cargo_and_ports(self, text: str, record: ShippingRecord):
        """Extract cargo type and port information from text."""
        if not text:
            return

        # Try to match cargo patterns first
        cargo_match = None
        for pattern in self.parser_config.cargo_patterns:
            if match := re.match(pattern, text, re.IGNORECASE):
                cargo_match = match
                break

        if cargo_match:
            record.cargo = cargo_match.group(0).strip()
            ports_text = text[cargo_match.end():].strip()
        else:
            # Look for port separators to determine where cargo ends
            if port_sep := re.search(r'\s+/\s+|\s+to\s+', text, re.IGNORECASE):
                # Extract cargo part before port separator
                cargo_part = text[:port_sep.start()].strip()
                # For unknown cargo types, be conservative - take only first word if it looks like a cargo name
                cargo_words = cargo_part.split()
                if len(cargo_words) == 1:
                    # Single word - likely a cargo type
                    record.cargo = cargo_words[0]
                elif len(cargo_words) == 2 and cargo_words[1].lower() in ['oil', 'acid', 'gas', 'fuel']:
                    # Two words where second is a cargo-related term
                    record.cargo = cargo_part
                elif len(cargo_words) >= 2:
                    # Multiple words - take first word only for unknown patterns
                    record.cargo = cargo_words[0]
                else:
                    record.cargo = cargo_part
                ports_text = text[port_sep.start():].strip()
            else:
                # No clear port separator, treat first word as cargo
                words = text.split()
                if len(words) >= 1:
                    record.cargo = words[0]
                ports_text = ""

        self._extract_ports_from_string(ports_text, record)

    def _extract_quantity_cargo_from_string(self, text: str, record: ShippingRecord):
        """Extract quantity and cargo from charterer format string."""
        if match := re.search(r'([\d,]+)\s*MT\s+(.*)', text, re.IGNORECASE):
            qty_str = match.group(1).replace(',', '')
            try:
                record.quantity_mt = float(qty_str)
            except ValueError:
                logger.warning(f"Could not parse quantity: {qty_str}")
            record.cargo = match.group(2).strip()

    def _extract_ports_from_string(self, ports_str: str, record: ShippingRecord):
        """Extract load and discharge ports from string."""
        if not ports_str:
            return

        # Skip delivery/redelivery instructions
        if re.search(r'\b(delivery|del|re-del)\b', ports_str, re.IGNORECASE):
            return

        # Clean freight information that might have leaked in
        for pattern in [r'[YU]?[Uu]sd?\s+[\d,\.]+', r'RNR', r'(?:hi|lo|mid)\s+\d+ies']:
            ports_str = re.sub(pattern, '', ports_str, flags=re.IGNORECASE).strip()

        # Extract ports based on separators
        if ' / ' in ports_str:
            parts = ports_str.split(' / ', 1)
            record.load_port, record.discharge_port = parts[0].strip(), parts[1].strip()
        elif to_match := re.search(r'\s+to\s+', ports_str, re.IGNORECASE):
            record.load_port = ports_str[:to_match.start()].strip()
            record.discharge_port = ports_str[to_match.end():].strip()

    def _finalize_record(self, record: ShippingRecord):
        """Parse laycan dates and calculate freight totals."""
        if record.laycan != "N/A":
            dates = self._parse_laycan(record.laycan)
            record.laycan_start_date = dates["start"]
            record.laycan_end_date = dates["end"]

        if (record.freight != "N/A" and
                isinstance(record.quantity_mt, (int, float)) and
                self.app_config.enable_freight_calculation):
            record.total_freight_usd = self._calculate_freight(record.freight, record.quantity_mt)

    def _parse_laycan(self, laycan_str: str) -> Dict[str, Optional[str]]:
        """Parse laycan string into start and end dates."""
        try:
            # Various laycan patterns
            patterns = [
                # 25-30 Jun or 06-10 June
                (r'(\d{1,2})-(\d{1,2})\s+(\w+)', self._parse_same_month_range),
                # 25 Jun – 5 July
                (r'(\d{1,2})\s+(\w+)\s*[–-]\s*(\d{1,2})\s+(\w+)', self._parse_cross_month_range),
                # end June – ely July
                (r'end\s+(\w+)\s*[–-]\s*ely\s+(\w+)', self._parse_end_to_early),
                # 1H July (first half)
                (r'1\s*[Hh]\s+(\w+)', self._parse_first_half),
                # 2H June (second half)
                (r'2[Hh]\s+(\w+)', self._parse_second_half),
                # Early/Ely June
                (r'[Ee](?:ly|arly)\s+(\w+)', self._parse_early_month),
                # mid Jul
                (r'mid\s+(\w+)', self._parse_mid_month),
                # end June
                (r'[Ee]nd\s+(\w+)', self._parse_end_month),
                # June dates (vague)
                (r'(\w+)\s+dates', self._parse_whole_month),
            ]

            for pattern, handler in patterns:
                if match := re.match(pattern, laycan_str, re.IGNORECASE):
                    return handler(match)

        except Exception as e:
            logger.warning(f"Failed to parse laycan '{laycan_str}': {e}")

        return {"start": None, "end": None}

    def _parse_same_month_range(self, match) -> Dict[str, Optional[str]]:
        """Parse date range within same month."""
        day1, day2, month_str = match.groups()
        month = self._get_month_number(month_str)
        if month:
            start = datetime(self.app_config.default_year, month, int(day1))
            end = datetime(self.app_config.default_year, month, int(day2))
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_cross_month_range(self, match) -> Dict[str, Optional[str]]:
        """Parse date range across months."""
        day1, month1_str, day2, month2_str = match.groups()
        month1, month2 = self._get_month_number(month1_str), self._get_month_number(month2_str)
        if month1 and month2:
            year2 = self.app_config.default_year if month2 >= month1 else self.app_config.default_year + 1
            start = datetime(self.app_config.default_year, month1, int(day1))
            end = datetime(year2, month2, int(day2))
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_end_to_early(self, match) -> Dict[str, Optional[str]]:
        """Parse 'end June - ely July' pattern."""
        month1_str, month2_str = match.groups()
        month1, month2 = self._get_month_number(month1_str), self._get_month_number(month2_str)
        if month1 and month2:
            year2 = self.app_config.default_year if month2 >= month1 else self.app_config.default_year + 1
            start = datetime(self.app_config.default_year, month1, 24)
            end = datetime(year2, month2, 10)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_first_half(self, match) -> Dict[str, Optional[str]]:
        """Parse first half of month (1H July)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 1)
            end = datetime(self.app_config.default_year, month, 15)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_second_half(self, match) -> Dict[str, Optional[str]]:
        """Parse second half of month (2H June)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 16)
            if month == 12:
                end = datetime(self.app_config.default_year, 12, 31)
            else:
                end = datetime(self.app_config.default_year, month + 1, 1) - timedelta(days=1)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_early_month(self, match) -> Dict[str, Optional[str]]:
        """Parse early month (Early June)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 1)
            end = datetime(self.app_config.default_year, month, 10)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_mid_month(self, match) -> Dict[str, Optional[str]]:
        """Parse middle of month (mid Jul)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 11)
            end = datetime(self.app_config.default_year, month, 20)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_end_month(self, match) -> Dict[str, Optional[str]]:
        """Parse end of month (end June)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 24)
            if month == 12:
                end = datetime(self.app_config.default_year, 12, 31)
            else:
                end = datetime(self.app_config.default_year, month + 1, 1) - timedelta(days=1)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _parse_whole_month(self, match) -> Dict[str, Optional[str]]:
        """Parse whole month (June dates)."""
        month = self._get_month_number(match.group(1))
        if month:
            start = datetime(self.app_config.default_year, month, 1)
            if month == 12:
                end = datetime(self.app_config.default_year, 12, 31)
            else:
                end = datetime(self.app_config.default_year, month + 1, 1) - timedelta(days=1)
            return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}
        return {"start": None, "end": None}

    def _get_month_number(self, month_str: str) -> Optional[int]:
        """Convert month string to number."""
        return self.months.get(month_str.lower()[:3])

    def _calculate_freight(self, freight_str: str, quantity: float) -> Union[float, str]:
        """Calculate total freight from freight string and quantity."""
        if freight_str == "RNR":
            return "N/A"

        try:
            # Clean typos if typo correction is enabled
            original_freight = freight_str
            if self.app_config.enable_typo_correction:
                freight_str = re.sub(r'^[YU]?[Uu]sd?', 'USD', freight_str)  # Fix YUsd, USd
                freight_str = re.sub(r'\bmiod\b', 'mid', freight_str)  # Fix miod
                freight_str = re.sub(r'\bhih\b', 'hi', freight_str)  # Fix hih

            freight_str = freight_str.replace(',', '')

            # Per metric ton rates
            if 'pmt' in freight_str.lower():
                if match := re.search(r'([\d\.]+)', freight_str):
                    return float(match.group(1)) * quantity

            # Million dollar amounts (including Lumpsum)
            elif re.search(r'\b[\d\.]+\s*M\b', freight_str, re.IGNORECASE):
                if match := re.search(r'([\d\.]+)', freight_str):
                    return float(match.group(1)) * 1_000_000

            # Thousand dollar amounts
            elif re.search(r'\bK\b', freight_str, re.IGNORECASE):
                if match := re.search(r'([\d\.]+)', freight_str):
                    return float(match.group(1)) * 1_000

            # Range estimates (e.g., "hi 40ies", "lo 90ies")
            elif re.search(r'(?:hi|lo|mid)\s+\d+ies', freight_str, re.IGNORECASE):
                if match := re.search(r'(\d+)ies', freight_str):
                    base_value = float(match.group(1))
                    # For "low" estimates in high numbers (like "lo 90ies"), treat as thousands
                    if 'lo' in freight_str.lower() and base_value > 50:
                        return base_value * 1_000
                    # For smaller values or "hi/mid", multiply by quantity (per ton rate)
                    elif base_value < 200:
                        return base_value * quantity
                    # For large base values, treat as total in thousands
                    else:
                        return base_value * 1_000

        except Exception as e:
            logger.warning(f"Failed to calculate freight for '{original_freight}': {e}")

        return "N/A"

    def save_to_excel(self, records: List[Dict], filename: str) -> bool:
        """Save parsed records to Excel file."""
        if not records:
            logger.warning("No records to save")
            return False

        try:
            df = pd.DataFrame(records)
            df.to_excel(filename, index=False, engine='openpyxl')
            logger.info(f"Saved {len(records)} records to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save to Excel: {e}")
            return False

    def get_parser_statistics(self) -> Dict:
        """Get parser configuration statistics."""
        return {
            'charterers_count': len(self.parser_config.charterers),
            'cargo_patterns_count': len(self.parser_config.cargo_patterns),
            'typo_correction_enabled': self.app_config.enable_typo_correction,
            'freight_calculation_enabled': self.app_config.enable_freight_calculation,
            'default_year': self.app_config.default_year
        }