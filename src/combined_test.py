#!/usr/bin/env python3
"""
Combined shipping parser and tests in one file.
Save as combined_test.py and run: python combined_test.py
"""

import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
import logging
import unittest
from unittest.mock import patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============ PARSER CODE ============

@dataclass
class ShippingRecord:
    """Simple data class for shipping records."""
    vessel_name: str = "N/A"
    cargo: str = "N/A"
    quantity_mt: Union[float, str] = "N/A"
    load_port: str = "N/A"
    discharge_port: str = "N/A"
    laycan: str = "N/A"
    laycan_start_date: Optional[str] = None
    laycan_end_date: Optional[str] = None
    freight: str = "N/A"
    total_freight_usd: Union[float, str] = "N/A"
    charterer: str = "N/A"

    def to_dict(self) -> Dict:
        return {
            "Vessel Name": self.vessel_name,
            "Cargo": self.cargo,
            "Quantity (MT)": self.quantity_mt,
            "Load Port": self.load_port,
            "Discharge Port": self.discharge_port,
            "Laycan": self.laycan,
            "Laycan Start Date": self.laycan_start_date,
            "Laycan End Date": self.laycan_end_date,
            "Freight": self.freight,
            "Total Freight (USD)": self.total_freight_usd,
            "Charterer": self.charterer,
        }


class ShippingDataParser:
    """Simple, working shipping data parser."""

    def __init__(self, default_year: int = 2024):
        self.default_year = default_year

        self.charterers = [
            "P66", "Neste", "Bunge", "Cargill", "Nova", "Olam", "ENI", "DGD",
            "SK Energy", "ICOF", "Kolmar", "Petroineos", "Wilmar", "GAM", "Aramco",
            "First Resources", "Alpha star", "St, Bernards Resources", "Mewah",
            "EFK", "Sime Darby", "Xiamen ITG", "Glencore", "SA Services", "CNR"
        ]

        self.months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

    def parse_shipping_data(self, text_data: str) -> List[Dict]:
        """Parse shipping data text into structured records."""
        if not text_data or not text_data.strip():
            return []

        records = []
        for line in text_data.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            try:
                record = self._parse_line(line)
                if record:
                    self._finalize_record(record)
                    records.append(record.to_dict())
            except Exception as e:
                logger.error(f"Error parsing line: {e}")
                continue

        logger.info(f"Parsed {len(records)} records")
        return records

    def _parse_line(self, line: str) -> Optional[ShippingRecord]:
        """Parse a single line."""
        if self._is_charterer_led(line):
            return self._parse_charterer_format(line)
        else:
            return self._parse_standard_format(line)

    def _is_charterer_led(self, line: str) -> bool:
        """Check if line starts with charterer."""
        return any(line.startswith(f"{c} /") for c in self.charterers)

    def _parse_charterer_format(self, line: str) -> ShippingRecord:
        """Parse P66 / Vessel / Cargo format."""
        record = ShippingRecord()
        parts = [p.strip() for p in line.split('/')]

        if len(parts) > 0:
            record.charterer = parts[0]
        if len(parts) > 1:
            record.vessel_name = parts[1]
        if len(parts) > 2:
            self._extract_quantity_cargo(parts[2], record)
        if len(parts) > 3:
            self._extract_ports(parts[3], record)
        if len(parts) > 4:
            remaining = ' / '.join(parts[4:])
            self._extract_laycan_freight(remaining, record)

        return record

    def _parse_standard_format(self, line: str) -> ShippingRecord:
        """Parse standard format."""
        record = ShippingRecord()
        work_line = self._clean_line(line)

        # Extract charterer
        for charterer in self.charterers:
            if re.search(rf'\b{re.escape(charterer)}\b', work_line, re.IGNORECASE):
                record.charterer = charterer
                work_line = re.sub(rf'\b{re.escape(charterer)}\b', '', work_line, flags=re.IGNORECASE).strip()
                break

        # Extract laycan and freight
        work_line = self._extract_laycan_freight(work_line, record)

        # Extract vessel, quantity, cargo, ports
        self._extract_vessel_cargo_ports(work_line, record)

        return record

    def _clean_line(self, line: str) -> str:
        """Remove interfering suffixes."""
        suffixes = [r'\s*-\s*Failed\s*$', r'\s*-\s*on\s+subs\s*$', r'\s+bss\s+\w+\s*$']
        for suffix in suffixes:
            line = re.sub(suffix, '', line, flags=re.IGNORECASE)
        return line

    def _extract_laycan_freight(self, text: str, record: ShippingRecord) -> str:
        """Extract laycan and freight."""
        work_text = text

        # Laycan patterns
        laycan_patterns = [
            r'\d{1,2}-\d{1,2}\s+\w+', r'\d{1,2}\s+\w+\s*[–-]\s*\d{1,2}\s+\w+',
            r'[12][Hh]\s+\w+', r'[Ee](?:ly|arly)\s+\w+', r'[Ee]nd\s+\w+',
            r'mid\s+\w+', r'\w+\s+dates'
        ]

        for pattern in laycan_patterns:
            if match := re.search(pattern, work_text, re.IGNORECASE):
                record.laycan = match.group(0).strip()
                work_text = work_text.replace(match.group(0), '').strip()
                break

        # Freight patterns
        freight_patterns = [
            r'USD\s+[\d,\.]+\s*M\s+Lumpsum', r'[YU]?[Uu]sd?\s+(?:hi|lo|mid)\s+[\d,\.]+\s*M',
            r'[YU]?[Uu]sd?\s+[\d,\.]+\s*M', r'[YU]?[Uu]sd?\s+[\d,\.]+\s+pmt',
            r'[YU]?[Uu]sd?\s+(?:low|hi|mid|miod|hih)\s+\d+ies',  # With Usd prefix
            r'(?:low|hi|mid|miod|hih)\s+\d+ies',  # Without Usd prefix
            r'RNR'
        ]

        for pattern in freight_patterns:
            if match := re.search(pattern, work_text, re.IGNORECASE):
                record.freight = match.group(0).strip()
                work_text = work_text.replace(match.group(0), '').strip()
                break

        return work_text

    def _extract_vessel_cargo_ports(self, text: str, record: ShippingRecord):
        """Extract vessel, quantity, cargo and ports."""
        # Quantity patterns
        qty_patterns = [
            r'(\d+-?\d*)\s*(?:ktons|ktrons|ktpns|Ktons|Mtons|MT)\b'
        ]

        qty_match = None
        for pattern in qty_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                qty_match = match
                break

        if qty_match:
            # Vessel before quantity
            vessel_part = text[:qty_match.start()].strip()
            vessel_part = re.sub(r'\([^)]*\)', '', vessel_part).strip()
            if vessel_part:
                record.vessel_name = vessel_part

            # Parse quantity
            qty_str = qty_match.group(1)
            if '-' in qty_str:
                qty_str = qty_str.split('-')[0]
            qty_str = qty_str.replace(',', '')

            try:
                qty_value = float(qty_str)
                unit = qty_match.group(0).lower()
                if any(x in unit for x in ['ktons', 'ktrons', 'ktpns']):
                    qty_value *= 1000
                record.quantity_mt = qty_value
            except ValueError:
                pass

            # Cargo and ports from remaining
            remaining = text[qty_match.end():].strip()
            self._extract_cargo_ports(remaining, record)

    def _extract_cargo_ports(self, text: str, record: ShippingRecord):
        """Extract cargo and ports."""
        if not text:
            return

        # Cargo patterns
        cargo_patterns = [
            r'UCO\s*\+\s*Tallow', r'UCO/UCOME/Bio\s+feedstock', r'Palm\s+oil',
            r'POP', r'BIOS', r'UCO', r'RPKO', r'S\.Acid', r'Chems', r'Palms'
        ]

        cargo_match = None
        for pattern in cargo_patterns:
            if match := re.match(pattern, text, re.IGNORECASE):
                cargo_match = match
                break

        if cargo_match:
            record.cargo = cargo_match.group(0).strip()
            ports_text = text[cargo_match.end():].strip()
        else:
            # Look for port separator
            if port_sep := re.search(r'\s+/\s+|\s+to\s+', text, re.IGNORECASE):
                record.cargo = text[:port_sep.start()].strip()
                ports_text = text[port_sep.start():].strip()
            else:
                ports_text = text

        self._extract_ports(ports_text, record)

    def _extract_quantity_cargo(self, text: str, record: ShippingRecord):
        """Extract quantity and cargo from charterer format."""
        if match := re.search(r'([\d,]+)\s*MT\s+(.*)', text, re.IGNORECASE):
            record.quantity_mt = float(match.group(1).replace(',', ''))
            record.cargo = match.group(2).strip()

    def _extract_ports(self, ports_str: str, record: ShippingRecord):
        """Extract load and discharge ports."""
        if not ports_str:
            return

        # Skip delivery instructions
        if re.search(r'\b(delivery|del|re-del)\b', ports_str, re.IGNORECASE):
            return

        # Clean freight info
        for pattern in [r'[YU]?[Uu]sd?\s+[\d,\.]+', r'RNR']:
            ports_str = re.sub(pattern, '', ports_str, flags=re.IGNORECASE).strip()

        # Extract ports
        if ' / ' in ports_str:
            parts = ports_str.split(' / ', 1)
            record.load_port, record.discharge_port = parts[0].strip(), parts[1].strip()
        elif to_match := re.search(r'\s+to\s+', ports_str, re.IGNORECASE):
            record.load_port = ports_str[:to_match.start()].strip()
            record.discharge_port = ports_str[to_match.end():].strip()

    def _finalize_record(self, record: ShippingRecord):
        """Parse dates and calculate freight."""
        if record.laycan != "N/A":
            dates = self._parse_laycan(record.laycan)
            record.laycan_start_date = dates["start"]
            record.laycan_end_date = dates["end"]

        if record.freight != "N/A" and isinstance(record.quantity_mt, (int, float)):
            record.total_freight_usd = self._calculate_freight(record.freight, record.quantity_mt)

    def _parse_laycan(self, laycan_str: str) -> Dict[str, Optional[str]]:
        """Parse laycan dates."""
        try:
            # Handle various patterns
            if match := re.match(r'(\d{1,2})-(\d{1,2})\s+(\w+)', laycan_str, re.IGNORECASE):
                day1, day2, month_str = match.groups()
                month = self._get_month_number(month_str)
                if month:
                    start = datetime(self.default_year, month, int(day1))
                    end = datetime(self.default_year, month, int(day2))
                    return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}

            elif match := re.match(r'1\s*[Hh]\s+(\w+)', laycan_str):
                month = self._get_month_number(match.group(1))
                if month:
                    start = datetime(self.default_year, month, 1)
                    end = datetime(self.default_year, month, 15)
                    return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}

            elif match := re.match(r'2[Hh]\s+(\w+)', laycan_str):
                month = self._get_month_number(match.group(1))
                if month:
                    start = datetime(self.default_year, month, 16)
                    end = datetime(self.default_year, month + 1, 1) - timedelta(days=1) if month < 12 else datetime(
                        self.default_year, 12, 31)
                    return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}

            elif match := re.match(r'[Ee](?:ly|arly)\s+(\w+)', laycan_str):
                month = self._get_month_number(match.group(1))
                if month:
                    start = datetime(self.default_year, month, 1)
                    end = datetime(self.default_year, month, 10)
                    return {"start": start.strftime('%Y-%m-%d'), "end": end.strftime('%Y-%m-%d')}

        except Exception as e:
            logger.warning(f"Failed to parse laycan '{laycan_str}': {e}")

        return {"start": None, "end": None}

    def _get_month_number(self, month_str: str) -> Optional[int]:
        """Convert month string to number."""
        return self.months.get(month_str.lower()[:3])

    def _calculate_freight(self, freight_str: str, quantity: float) -> Union[float, str]:
        """Calculate total freight."""
        if freight_str == "RNR":
            return "N/A"

        try:
            # Clean typos
            freight_str = re.sub(r'^[YU]?[Uu]sd?', 'Usd', freight_str)
            freight_str = re.sub(r'\bmiod\b', 'mid', freight_str)
            freight_str = re.sub(r'\bhih\b', 'hi', freight_str)
            freight_str = freight_str.replace(',', '')

            if 'pmt' in freight_str.lower():
                if match := re.search(r'([\d\.]+)', freight_str):
                    return float(match.group(1)) * quantity

            elif re.search(r'\bM\b', freight_str, re.IGNORECASE):
                if match := re.search(r'([\d\.]+)', freight_str):
                    return float(match.group(1)) * 1_000_000

            elif re.search(r'(?:hi|lo|mid)\s+\d+ies', freight_str, re.IGNORECASE):
                if match := re.search(r'(\d+)ies', freight_str):
                    base_value = float(match.group(1))
                    return base_value * quantity if base_value < 200 else base_value * 1_000

        except Exception as e:
            logger.warning(f"Failed to calculate freight: {e}")

        return "N/A"

    def save_to_excel(self, records: List[Dict], filename: str = "shipping_data.xlsx") -> bool:
        """Save records to Excel."""
        if not records:
            logger.warning("No records to save")
            return False

        try:
            df = pd.DataFrame(records)
            df.to_excel(filename, index=False, engine='openpyxl')
            logger.info(f"Saved {len(records)} records to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save Excel: {e}")
            return False


# ============ TESTS ============

class TestShippingParser(unittest.TestCase):

    def setUp(self):
        self.parser = ShippingDataParser(default_year=2024)

    def test_basic_parsing(self):
        """Test basic parsing functionality."""
        test_input = "Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova"
        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['Vessel Name'], 'Dai Thanh')
        self.assertEqual(record['Cargo'], 'POP')
        self.assertEqual(record['Quantity (MT)'], 12000.0)
        self.assertEqual(record['Charterer'], 'Nova')

    def test_charterer_format(self):
        """Test charterer-led format."""
        test_input = "P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum"
        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['Charterer'], 'P66')
        self.assertEqual(record['Vessel Name'], 'Seaways Moment')
        self.assertEqual(record['Quantity (MT)'], 32000.0)

    def test_new_patterns(self):
        """Test new patterns from additional data."""
        test_input = "Sheng Hang Hua 13  5ktpns RPKO  LBK  / Zhapu   Usd 40 pmt  4-10 July  First Resources"
        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['Vessel Name'], 'Sheng Hang Hua 13')
        self.assertEqual(record['Cargo'], 'RPKO')
        self.assertEqual(record['Quantity (MT)'], 5000.0)  # ktpns converted
        self.assertEqual(record['Charterer'], 'First Resources')

    def test_typo_handling(self):
        """Test handling of common typos."""
        test_input = "Goldstar Shine  3ktons RPKO  PGG / Zhangjiagnag  hih 40ies  1H July   Alpha star"
        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['Freight'], 'hih 40ies')  # Preserved but calculated correctly
        self.assertEqual(record['Total Freight (USD)'], 120000.0)

    def test_laycan_parsing(self):
        """Test laycan date parsing."""
        test_cases = [
            ("4-10 July", "2024-07-04", "2024-07-10"),
            ("1H July", "2024-07-01", "2024-07-15"),
            ("2H July", "2024-07-16", "2024-07-31"),
        ]

        for laycan_str, expected_start, expected_end in test_cases:
            result = self.parser._parse_laycan(laycan_str)
            self.assertEqual(result["start"], expected_start)
            self.assertEqual(result["end"], expected_end)

    def test_empty_input(self):
        """Test empty input handling."""
        self.assertEqual(self.parser.parse_shipping_data(""), [])
        self.assertEqual(self.parser.parse_shipping_data("   \n  "), [])


if __name__ == '__main__':
    print("🧪 Running Shipping Parser Tests...")
    unittest.main(verbosity=2)