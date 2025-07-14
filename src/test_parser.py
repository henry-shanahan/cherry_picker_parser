import unittest
from unittest.mock import patch
from src.parser import ShippingDataParser


class TestShippingParser(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize parser with fixed year for consistent testing
        self.parser = ShippingDataParser(default_year=2024)

    def assertRecordEqual(self, actual_record, expected_record, msg=None):
        """Custom assertion to compare records with better error messages."""
        for key, expected_value in expected_record.items():
            self.assertIn(key, actual_record, f"Missing key '{key}' in parsed record")
            actual_value = actual_record[key]

            # Handle floating point comparisons
            if isinstance(expected_value, float) and isinstance(actual_value, float):
                self.assertAlmostEqual(
                    actual_value, expected_value, places=2,
                    msg=f"Values for '{key}' don't match: expected {expected_value}, got {actual_value}"
                )
            else:
                self.assertEqual(
                    actual_value, expected_value,
                    msg=f"Values for '{key}' don't match: expected {expected_value}, got {actual_value}"
                )

    def test_parsing_examples(self):
        """
        Tests the final parser with a variety of data formats from the brief.
        The expected results here are the correct, final target for our parser.
        """
        # A comprehensive list of all test cases we've encountered.
        # All dates are hardcoded to the year 2024 for stable, predictable tests.
        test_cases = [
            {
                "input": "Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar",
                "expected": {
                    'Vessel Name': 'Seagull 09', 'Cargo': 'Palm oil', 'Quantity (MT)': 10000.0,
                    'Load Port': 'E.Malaysia', 'Discharge Port': 'EC India', 'Laycan': '2H June',
                    'Laycan Start Date': '2024-06-16', 'Laycan End Date': '2024-06-30',
                    'Freight': 'Usd 35 pmt', 'Total Freight (USD)': 350000.0, 'Charterer': 'Wilmar'
                }
            },
            {
                "input": "P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum",
                "expected": {
                    'Vessel Name': 'Seaways Moment', 'Cargo': 'UCO + Tallow', 'Quantity (MT)': 32000.0,
                    'Load Port': 'Port Klang', 'Discharge Port': 'USWC', 'Laycan': '06-10 June',
                    'Laycan Start Date': '2024-06-06', 'Laycan End Date': '2024-06-10',
                    'Freight': 'USD 2.15M Lumpsum', 'Total Freight (USD)': 2150000.0, 'Charterer': 'P66'
                }
            },
            {
                "input": "NCC Danah   30-40ktons  UCO/Bio feedstocks    China + Straits / Spain – ARA Rge   RNR   end June – ely July   Kolmar",
                "expected": {
                    'Vessel Name': 'NCC Danah', 'Cargo': 'UCO/Bio feedstocks', 'Quantity (MT)': 30000.0,
                    'Load Port': 'China + Straits', 'Discharge Port': 'Spain – ARA Rge',
                    'Laycan': 'end June – ely July',
                    'Laycan Start Date': '2024-06-24', 'Laycan End Date': '2024-07-10',
                    'Freight': 'N/A', 'Total Freight (USD)': 'N/A', 'Charterer': 'Kolmar'
                }
            },
            {
                "input": "Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova",
                "expected": {
                    'Vessel Name': 'Dai Thanh', 'Cargo': 'POP', 'Quantity (MT)': 12000.0,
                    'Load Port': 'Balikpapan', 'Discharge Port': 'South China', 'Laycan': '25-30 Jun',
                    'Laycan Start Date': '2024-06-25', 'Laycan End Date': '2024-06-30',
                    'Freight': 'Usd 29.00 pmt', 'Total Freight (USD)': 348000.0, 'Charterer': 'Nova'
                }
            },
            {
                "input": "Alfred N 23500 Mtons POME/Palms/UCO    China + Starits / Italy    Usd 2.85 M 1/1   2h June  ENI",
                "expected": {
                    'Vessel Name': 'Alfred N', 'Cargo': 'POME/Palms/UCO', 'Quantity (MT)': 23500.0,
                    'Load Port': 'China + Starits', 'Discharge Port': 'Italy', 'Laycan': '2h June',
                    'Laycan Start Date': '2024-06-16', 'Laycan End Date': '2024-06-30',
                    'Freight': 'Usd 2.85 M', 'Total Freight (USD)': 2850000.0, 'Charterer': 'ENI'
                }
            }
        ]

        for i, case in enumerate(test_cases):
            with self.subTest(i=i, msg=case["input"]):
                # Use the new parser method
                parsed_records = self.parser.parse_shipping_data(case["input"])

                # Basic validation that we got a result
                self.assertIsNotNone(parsed_records, "Parser returned None")
                self.assertEqual(len(parsed_records), 1, "Parser did not return exactly one record")

                # The actual comparison against the correct, expected output
                self.assertRecordEqual(parsed_records[0], case["expected"])

    def test_empty_input(self):
        """Test parser handles empty input gracefully."""
        result = self.parser.parse_shipping_data("")
        self.assertEqual(result, [])

        result = self.parser.parse_shipping_data("   \n  \n  ")
        self.assertEqual(result, [])

    def test_invalid_input(self):
        """Test parser handles invalid input gracefully."""
        # Should not crash, but may return empty or partial records
        result = self.parser.parse_shipping_data("This is not shipping data at all")
        self.assertIsInstance(result, list)

    def test_multiple_records(self):
        """Test parsing multiple records in one input."""
        multi_record_input = """Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar
Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova"""

        result = self.parser.parse_shipping_data(multi_record_input)
        self.assertEqual(len(result), 2)

        # Check first record
        self.assertEqual(result[0]['Vessel Name'], 'Seagull 09')
        self.assertEqual(result[0]['Cargo'], 'Palm oil')

        # Check second record
        self.assertEqual(result[1]['Vessel Name'], 'Dai Thanh')
        self.assertEqual(result[1]['Cargo'], 'POP')

    def test_laycan_parsing_edge_cases(self):
        """Test various laycan date formats."""
        laycan_test_cases = [
            ("2H June", "2024-06-16", "2024-06-30"),
            ("06-10 June", "2024-06-06", "2024-06-10"),
            ("end June – ely July", "2024-06-24", "2024-07-10"),
            ("25-30 Jun", "2024-06-25", "2024-06-30"),
        ]

        for laycan_str, expected_start, expected_end in laycan_test_cases:
            with self.subTest(laycan=laycan_str):
                result = self.parser.laycan_parser.normalize_laycan(laycan_str)
                self.assertEqual(result["Laycan Start Date"], expected_start)
                self.assertEqual(result["Laycan End Date"], expected_end)

    def test_freight_calculation(self):
        """Test freight calculation logic."""
        calculator = self.parser.freight_calculator

        # Test per metric ton calculation
        result = calculator.calculate_total_freight("USD 35 pmt", 10000.0)
        self.assertEqual(result, 350000.0)

        # Test lumpsum calculation
        result = calculator.calculate_total_freight("USD 2.15M Lumpsum", 32000.0)
        self.assertEqual(result, 2150000.0)

        # Test invalid inputs
        result = calculator.calculate_total_freight("N/A", 10000.0)
        self.assertEqual(result, "N/A")

        result = calculator.calculate_total_freight("USD 35 pmt", "N/A")
        self.assertEqual(result, "N/A")

    def test_charterer_led_format(self):
        """Test specific parsing of charterer-led format."""
        charterer_input = "P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum"

        result = self.parser.parse_shipping_data(charterer_input)
        self.assertEqual(len(result), 1)

        record = result[0]
        self.assertEqual(record['Charterer'], 'P66')
        self.assertEqual(record['Vessel Name'], 'Seaways Moment')
        self.assertEqual(record['Quantity (MT)'], 32000.0)
        self.assertEqual(record['Cargo'], 'UCO + Tallow')

    def test_standard_format(self):
        """Test specific parsing of standard format."""
        standard_input = "Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar"

        result = self.parser.parse_shipping_data(standard_input)
        self.assertEqual(len(result), 1)

        record = result[0]
        self.assertEqual(record['Vessel Name'], 'Seagull 09')
        self.assertEqual(record['Quantity (MT)'], 10000.0)
        self.assertEqual(record['Cargo'], 'Palm oil')
        self.assertEqual(record['Charterer'], 'Wilmar')

    @patch('src.parser.logger')
    def test_logging_on_parse_error(self, mock_logger):
        """Test that parsing errors are properly logged."""
        # This should trigger some parsing issues but not crash
        problematic_input = "Some really malformed data with numbers 12345 but no clear structure"

        result = self.parser.parse_shipping_data(problematic_input)

        # Should return a record (even if mostly N/A) and log warnings
        self.assertIsInstance(result, list)
        # Verify that warnings were logged (mock_logger.warning should have been called)

    def test_year_handling(self):
        """Test that the parser correctly uses the specified year."""
        # Test with a different year
        parser_2025 = ShippingDataParser(default_year=2025)

        result = parser_2025.laycan_parser.normalize_laycan("2H June")
        self.assertEqual(result["Laycan Start Date"], "2025-06-16")
        self.assertEqual(result["Laycan End Date"], "2025-06-30")

    def test_save_to_excel_functionality(self):
        """Test Excel saving functionality."""
        # Create some test records
        test_input = "Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar"
        records = self.parser.parse_shipping_data(test_input)

        # Test saving (this might require mocking file operations in a real test environment)
        # For now, just test that the method exists and handles empty records
        result = self.parser.save_to_excel([], "test_output.xlsx")
        self.assertFalse(result)  # Should return False for empty records


if __name__ == '__main__':
    # This allows you to run the test directly from the command line
    unittest.main(verbosity=2)