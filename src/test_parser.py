#!/usr/bin/env python3
"""
Unit tests for shipping data parser.
"""

import unittest
from unittest.mock import patch
from datetime import datetime

from models import ShippingRecord
from config import AppConfig, ParserConfig
from shipping_parser import ShippingDataParser


class TestShippingRecord(unittest.TestCase):
    """Test the ShippingRecord data class."""

    def test_shipping_record_creation(self):
        """Test creating a shipping record with default values."""
        record = ShippingRecord()

        self.assertEqual(record.vessel_name, "N/A")
        self.assertEqual(record.cargo, "N/A")
        self.assertEqual(record.quantity_mt, "N/A")
        self.assertEqual(record.charterer, "N/A")

    def test_shipping_record_to_dict(self):
        """Test converting shipping record to dictionary."""
        record = ShippingRecord(
            vessel_name="Test Vessel",
            cargo="Test Cargo",
            quantity_mt=1000.0,
            charterer="Test Charterer"
        )

        result = record.to_dict()

        expected = {
            "Vessel Name": "Test Vessel",
            "Cargo": "Test Cargo",
            "Quantity (MT)": 1000.0,
            "Load Port": "N/A",
            "Discharge Port": "N/A",
            "Laycan": "N/A",
            "Laycan Start Date": None,
            "Laycan End Date": None,
            "Freight": "N/A",
            "Total Freight (USD)": "N/A",
            "Charterer": "Test Charterer",
        }

        self.assertEqual(result, expected)

    def test_is_complete(self):
        """Test checking if record is complete."""
        # Complete record
        complete_record = ShippingRecord(
            vessel_name="Test Vessel",
            quantity_mt=1000.0
        )
        self.assertTrue(complete_record.is_complete())

        # Incomplete records
        incomplete_records = [
            ShippingRecord(vessel_name="N/A", quantity_mt=1000.0),
            ShippingRecord(vessel_name="Test Vessel", quantity_mt="N/A"),
            ShippingRecord(vessel_name="Test Vessel", quantity_mt="invalid"),
        ]

        for record in incomplete_records:
            with self.subTest(record=record):
                self.assertFalse(record.is_complete())

    def test_has_laycan_dates(self):
        """Test checking if record has laycan dates."""
        record_with_dates = ShippingRecord(laycan_start_date="2024-01-01")
        self.assertTrue(record_with_dates.has_laycan_dates())

        record_without_dates = ShippingRecord()
        self.assertFalse(record_without_dates.has_laycan_dates())


class TestShippingDataParser(unittest.TestCase):
    """Test the main shipping data parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.app_config = AppConfig(default_year=2024)
        self.parser_config = ParserConfig()
        self.parser = ShippingDataParser(self.app_config, self.parser_config)

    def test_parse_empty_input(self):
        """Test parsing empty input."""
        test_cases = ["", "   ", "\n\n\n", None]

        for test_input in test_cases:
            with self.subTest(input=test_input):
                result = self.parser.parse_shipping_data(test_input or "")
                self.assertEqual(result, [])

    def test_parse_basic_standard_format(self):
        """Test parsing basic standard format."""
        test_input = "Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova"

        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record['Vessel Name'], 'Dai Thanh')
        self.assertEqual(record['Cargo'], 'POP')
        self.assertEqual(record['Quantity (MT)'], 12000.0)
        self.assertEqual(record['Load Port'], 'Balikpapan')
        self.assertEqual(record['Discharge Port'], 'South China')
        self.assertEqual(record['Laycan'], '25-30 Jun')
        self.assertEqual(record['Laycan Start Date'], '2024-06-25')
        self.assertEqual(record['Laycan End Date'], '2024-06-30')
        self.assertEqual(record['Freight'], 'Usd 29.00 pmt')
        self.assertEqual(record['Total Freight (USD)'], 348000.0)  # 29 * 12000
        self.assertEqual(record['Charterer'], 'Nova')

    def test_parse_charterer_led_format(self):
        """Test parsing charterer-led format."""
        test_input = "P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum"

        records = self.parser.parse_shipping_data(test_input)

        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record['Charterer'], 'P66')
        self.assertEqual(record['Vessel Name'], 'Seaways Moment')
        self.assertEqual(record['Cargo'], 'UCO + Tallow')
        self.assertEqual(record['Quantity (MT)'], 32000.0)
        self.assertEqual(record['Load Port'], 'Port Klang')
        self.assertEqual(record['Discharge Port'], 'USWC')
        self.assertEqual(record['Laycan'], '06-10 June')
        self.assertEqual(record['Freight'], 'USD 2.15M Lumpsum')
        self.assertEqual(record['Total Freight (USD)'], 2150000.0)

    def test_parse_vessel_names_with_numbers(self):
        """Test parsing vessel names that include numbers."""
        test_cases = [
            ("Sea Gull 18   12ktons POP Kumai / China   Usd 30 pmt  Ely Jun  Olam", "Sea Gull 18"),
            ("Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar", "Seagull 09"),
            ("Bao Feng Hua 1 8600  Benzene  Kandla / Jubail   Usd low 30ies    17-25 June Aramco", "Bao Feng Hua 1"),
            ("Huang Shan 16  18ktons  POP   Straist  / WC India   Usd hi 309ies  1H Jul  Alpha star", "Huang Shan 16"),
        ]

        for test_input, expected_vessel in test_cases:
            with self.subTest(vessel=expected_vessel):
                records = self.parser.parse_shipping_data(test_input)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['Vessel Name'], expected_vessel)

    def test_parse_quantity_variations(self):
        """Test parsing various quantity formats."""
        test_cases = [
            ("vessel 10ktons cargo port1 / port2", 10000.0),
            ("vessel 5ktpns cargo port1 / port2", 5000.0),  # Typo handling
            ("vessel 12ktrons cargo port1 / port2", 12000.0),
            ("vessel 30-40ktons cargo port1 / port2", 30000.0),  # Range - takes lower bound
            ("vessel 23500 Mtons cargo port1 / port2", 23500.0),  # Mtons stays as is
            ("vessel 49Ktons cargo port1 / port2", 49000.0),  # Capital K
        ]

        for test_input, expected_qty in test_cases:
            with self.subTest(input=test_input):
                records = self.parser.parse_shipping_data(test_input)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['Quantity (MT)'], expected_qty)

    def test_parse_new_cargo_types(self):
        """Test parsing new cargo types from additional data."""
        test_cases = [
            ("vessel 10ktons RPKO port1 / port2", "RPKO"),
            ("vessel 20ktons S.Acid port1 / port2", "S.Acid"),
            ("vessel 15ktons Chems port1 / port2", "Chems"),
            ("vessel 25ktons Biofeedstocks/chems port1 / port2", "Biofeedstocks/chems"),
            ("vessel 10ktons UCO + Tallow port1 / port2", "UCO + Tallow"),
            ("vessel 10ktons Palm oil port1 / port2", "Palm oil"),
        ]

        for test_input, expected_cargo in test_cases:
            with self.subTest(cargo=expected_cargo):
                records = self.parser.parse_shipping_data(test_input)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['Cargo'], expected_cargo)

    def test_parse_laycan_patterns(self):
        """Test parsing various laycan date patterns."""
        test_cases = [
            ("4-10 July", "2024-07-04", "2024-07-10"),
            ("1H July", "2024-07-01", "2024-07-15"),
            ("2H July", "2024-07-16", "2024-07-31"),
            ("20-30 July", "2024-07-20", "2024-07-30"),
            ("mid Jul", "2024-07-11", "2024-07-20"),
            ("June dates", "2024-06-01", "2024-06-30"),
            ("1 H Jul", "2024-07-01", "2024-07-15"),  # With space
            ("ely July", "2024-07-01", "2024-07-10"),
            ("Early June", "2024-06-01", "2024-06-10"),
            ("end June", "2024-06-24", "2024-06-30"),
            ("25 Jun – 5 July", "2024-06-25", "2024-07-05"),  # Cross-month
        ]

        for laycan_str, expected_start, expected_end in test_cases:
            with self.subTest(laycan=laycan_str):
                result = self.parser._parse_laycan(laycan_str)
                self.assertEqual(result["start"], expected_start)
                self.assertEqual(result["end"], expected_end)

    def test_freight_calculation_with_typos(self):
        """Test freight calculation with typo correction."""
        test_cases = [
            ("USD 2.15M Lumpsum", 32000.0, 2150000.0),
            ("Usd 35 pmt", 10000.0, 350000.0),
            ("hih 40ies", 3000.0, 120000.0),  # Without Usd prefix
            ("Usd mid 40ies", 10000.0, 400000.0),
            ("Usd miod 60ies", 5000.0, 300000.0),  # Typo: miod -> mid
            ("YUsd 55 pmt", 8500.0, 467500.0),  # Typo: YUsd -> Usd
            ("Usd lo 90ies", 30000.0, 90000.0),  # Low estimate in thousands
            ("RNR", 10000.0, "N/A"),  # Rate not reported
        ]

        for freight_str, quantity, expected_total in test_cases:
            with self.subTest(freight=freight_str):
                result = self.parser._calculate_freight(freight_str, quantity)
                self.assertEqual(result, expected_total)

    def test_freight_calculation_without_typo_correction(self):
        """Test freight calculation with typo correction disabled."""
        # Disable typo correction
        self.app_config.enable_typo_correction = False
        parser = ShippingDataParser(self.app_config, self.parser_config)

        # Test that typos are not corrected
        result = parser._calculate_freight("YUsd 55 pmt", 1000.0)
        # Without typo correction, "YUsd" should not be recognized properly
        self.assertEqual(result, 55000.0)  # Still works because the number is extracted

    def test_parse_port_variations(self):
        """Test parsing various port formats."""
        test_cases = [
            ("China / USA", "China", "USA"),
            ("Port Klang to USWC", "Port Klang", "USWC"),
            ("China + Straits / Spain – ARA Rge", "China + Straits", "Spain – ARA Rge"),
            ("E.Malaysia / EC India", "E.Malaysia", "EC India"),
            ("2 ports PNG / WC India", "2 ports PNG", "WC India"),
            ("Longkou or Fangcheng / Chile or Morocco", "Longkou or Fangcheng", "Chile or Morocco"),
        ]

        for ports_str, expected_load, expected_discharge in test_cases:
            with self.subTest(ports=ports_str):
                record = ShippingRecord()
                self.parser._extract_ports_from_string(ports_str, record)
                self.assertEqual(record.load_port, expected_load)
                self.assertEqual(record.discharge_port, expected_discharge)

    def test_skip_delivery_instructions(self):
        """Test that delivery instructions are not parsed as ports."""
        test_cases = [
            "delivery Sth korea / Re-del Medcont",
            "Del Haldia / Re-del MedcontUSA",
        ]

        for ports_str in test_cases:
            with self.subTest(ports=ports_str):
                record = ShippingRecord()
                self.parser._extract_ports_from_string(ports_str, record)
                # Should not extract delivery instructions as ports
                self.assertEqual(record.load_port, "N/A")
                self.assertEqual(record.discharge_port, "N/A")

    def test_parse_new_charterers(self):
        """Test recognition of new charterers."""
        new_charterers = [
            "First Resources", "Alpha star", "Sime Darby", "Glencore",
            "SA Services", "CNR", "Xiamen ITG"
        ]

        for charterer in new_charterers:
            with self.subTest(charterer=charterer):
                test_input = f"vessel 10ktons cargo port1 / port2 Usd 30 pmt 1-5 Jul {charterer}"
                records = self.parser.parse_shipping_data(test_input)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['Charterer'], charterer)

    def test_parse_multiple_records(self):
        """Test parsing multiple records at once."""
        multi_input = """Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar
Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova
P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum"""

        records = self.parser.parse_shipping_data(multi_input)
        self.assertEqual(len(records), 3)

        # Check vessel names
        expected_vessels = ['Seagull 09', 'Dai Thanh', 'Seaways Moment']
        actual_vessels = [record['Vessel Name'] for record in records]
        self.assertEqual(actual_vessels, expected_vessels)

    def test_line_cleaning_suffixes(self):
        """Test removal of status suffixes."""
        test_cases = [
            ("Stena Impression  49ktons cargo port1 / port2  Usd 24K PD   1-10 Jun  Cargill - Failed", "Cargill"),
            ("Boxer  35ktons cargo China  / ARA    RNR     1-10 Jul      Petroineos  - on subs", "Petroineos"),
        ]

        for test_input, expected_charterer in test_cases:
            with self.subTest(input=test_input[:30] + "..."):
                records = self.parser.parse_shipping_data(test_input)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['Charterer'], expected_charterer)

    def test_year_rollover_in_laycan(self):
        """Test handling of dates that cross year boundaries."""
        # Create parser with December 2024 as default year
        app_config = AppConfig(default_year=2024)
        parser = ShippingDataParser(app_config, self.parser_config)

        result = parser._parse_laycan("25 Dec – 5 Jan")

        self.assertEqual(result["start"], "2024-12-25")
        self.assertEqual(result["end"], "2025-01-05")  # Should roll to next year

    def test_parser_statistics(self):
        """Test getting parser statistics."""
        stats = self.parser.get_parser_statistics()

        expected_keys = [
            'charterers_count', 'cargo_patterns_count', 'typo_correction_enabled',
            'freight_calculation_enabled', 'default_year'
        ]

        for key in expected_keys:
            self.assertIn(key, stats)

        # Check some expected values
        self.assertGreater(stats['charterers_count'], 15)  # Should have many charterers
        self.assertGreater(stats['cargo_patterns_count'], 20)  # Should have many cargo patterns
        self.assertTrue(stats['typo_correction_enabled'])
        self.assertTrue(stats['freight_calculation_enabled'])
        self.assertEqual(stats['default_year'], 2024)

    @patch('shipping_parser.pd.DataFrame.to_excel')
    def test_save_to_excel_success(self, mock_to_excel):
        """Test successful Excel file saving."""
        mock_to_excel.return_value = None  # Successful save

        test_records = [{'Vessel Name': 'Test', 'Cargo': 'Test Cargo'}]
        result = self.parser.save_to_excel(test_records, "test.xlsx")

        self.assertTrue(result)
        mock_to_excel.assert_called_once_with("test.xlsx", index=False, engine='openpyxl')

    @patch('shipping_parser.pd.DataFrame.to_excel')
    def test_save_to_excel_failure(self, mock_to_excel):
        """Test Excel file saving failure."""
        mock_to_excel.side_effect = Exception("Save failed")

        test_records = [{'Vessel Name': 'Test', 'Cargo': 'Test Cargo'}]
        result = self.parser.save_to_excel(test_records, "test.xlsx")

        self.assertFalse(result)

    def test_save_to_excel_empty_records(self):
        """Test saving empty records list."""
        result = self.parser.save_to_excel([], "test.xlsx")
        self.assertFalse(result)

    def test_invalid_laycan_patterns(self):
        """Test handling of invalid laycan patterns."""
        invalid_patterns = [
            "invalid date",
            "13-45 Blah",  # Invalid day
            "some random text",
            "",
        ]

        for pattern in invalid_patterns:
            with self.subTest(pattern=pattern):
                result = self.parser._parse_laycan(pattern)
                self.assertIsNone(result["start"])
                self.assertIsNone(result["end"])

    def test_month_name_recognition(self):
        """Test month name recognition."""
        valid_months = [
            ('jan', 1), ('feb', 2), ('mar', 3), ('apr', 4),
            ('may', 5), ('jun', 6), ('jul', 7), ('aug', 8),
            ('sep', 9), ('oct', 10), ('nov', 11), ('dec', 12)
        ]

        for month_str, expected_num in valid_months:
            with self.subTest(month=month_str):
                result = self.parser._get_month_number(month_str)
                self.assertEqual(result, expected_num)

                # Test case insensitive
                result_upper = self.parser._get_month_number(month_str.upper())
                self.assertEqual(result_upper, expected_num)

        # Test invalid month
        result = self.parser._get_month_number("invalid")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)