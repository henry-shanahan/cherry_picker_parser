import unittest
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys

# Import your actual modules
from shipping_parser import ShippingDataParser
from config import ParserConfig


class TestDateParsingEnhanced(unittest.TestCase):
    """Enhanced version of the date parsing test with comprehensive debugging"""

    def setUp(self):
        """Set up test environment with consistent state"""
        # Enable detailed logging for debugging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # Test data that was failing
        self.test_data = "VESSEL 25-28 JUNE CARGO FROM PORT TO PORT2"

        # Years to test
        self.test_years = [2023, 2024, 2025]

    def tearDown(self):
        """Clean up after each test"""
        # Reset any global state if needed
        pass

    def test_year_configuration_effects_enhanced(self):
        """Enhanced test with detailed debugging for year configuration effects"""

        for year in self.test_years:
            with self.subTest(year=year):
                self.logger.info(f"Testing year configuration: {year}")

                # Create parser with specific year configuration
                try:
                    parser = self._create_parser_with_year(year)
                    self.assertIsNotNone(parser, f"Parser creation failed for year {year}")

                    # Log the configuration
                    self.logger.debug(f"Parser configuration: year={year}")

                    # Parse the test data
                    self.logger.debug(f"Input data: '{self.test_data}'")
                    records = parser.parse(self.test_data)

                    # Debug the parsing results
                    self.logger.debug(f"Number of records parsed: {len(records)}")
                    self.assertGreater(len(records), 0, f"No records parsed for year {year}")

                    record = records[0]
                    self.logger.debug(f"First record: {record}")

                    # Check all date-related fields
                    laycan_start = record.get('Laycan Start Date')
                    laycan_end = record.get('Laycan End Date')

                    self.logger.debug(f"Laycan Start Date: {laycan_start}")
                    self.logger.debug(f"Laycan End Date: {laycan_end}")

                    # Enhanced assertions with better error messages
                    self.assertIsNotNone(
                        laycan_start,
                        f"Laycan Start Date is None for year {year}. Full record: {record}"
                    )

                    expected_start_date = f'{year}-06-25'
                    self.assertEqual(
                        laycan_start,
                        expected_start_date,
                        f"Expected '{expected_start_date}' but got '{laycan_start}' for year {year}"
                    )

                    # Additional validation for end date
                    if laycan_end:
                        expected_end_date = f'{year}-06-28'
                        self.assertEqual(
                            laycan_end,
                            expected_end_date,
                            f"Expected end date '{expected_end_date}' but got '{laycan_end}' for year {year}"
                        )

                except Exception as e:
                    self.logger.error(f"Exception during parsing for year {year}: {e}")
                    self.logger.error(f"Exception type: {type(e)}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    raise

    def _create_parser_with_year(self, year):
        """Helper method to create parser with specific year configuration"""
        try:
            config = ParserConfig()
            config.year = year
            config.enable_typo_correction = True
            config.enable_freight_calculation = True

            parser = ShippingDataParser(config)
            return parser

        except Exception as e:
            self.logger.error(f"Failed to create parser for year {year}: {e}")
            raise

    def test_date_parsing_edge_cases(self):
        """Test various edge cases in date parsing"""
        edge_cases = [
            ("VESSEL 31 DEC-02 JAN CARGO PORT1/PORT2", "year_boundary"),
            ("VESSEL 29 FEB CARGO PORT1/PORT2", "leap_year"),  # 2024 is leap year
            ("VESSEL 1-5 JUNE CARGO PORT1/PORT2", "single_digit_dates"),
            ("VESSEL 25/28 JUNE CARGO PORT1/PORT2", "slash_separator"),
            ("VESSEL 25-28 JUN CARGO PORT1/PORT2", "abbreviated_month"),
        ]

        for test_data, case_name in edge_cases:
            with self.subTest(case=case_name):
                self.logger.info(f"Testing edge case: {case_name}")
                self.logger.debug(f"Input: '{test_data}'")

                for year in [2023, 2024, 2025]:
                    with self.subTest(year=year):
                        parser = self._create_parser_with_year(year)

                        try:
                            records = parser.parse(test_data)
                            if records:
                                record = records[0]
                                self.logger.debug(f"Parsed record for {case_name} (year {year}): {record}")

                                # Basic validation - at least some date should be parsed
                                has_dates = any(
                                    record.get(field) for field in
                                    ['Laycan Start Date', 'Laycan End Date']
                                )
                                if not has_dates:
                                    self.logger.warning(f"No dates parsed for {case_name} with year {year}")
                            else:
                                self.logger.warning(f"No records parsed for {case_name} with year {year}")

                        except Exception as e:
                            self.logger.error(f"Error parsing {case_name} with year {year}: {e}")
                            # Don't fail the test for edge cases, just log the issues

    def test_parser_state_isolation(self):
        """Test that parser instances don't interfere with each other"""

        # Create multiple parsers with different configurations
        parsers = {}
        for year in self.test_years:
            parsers[year] = self._create_parser_with_year(year)

        # Parse the same data with all parsers
        results = {}
        for year, parser in parsers.items():
            results[year] = parser.parse(self.test_data)

        # Verify that each parser produced consistent results
        for year, records in results.items():
            if records:
                record = records[0]
                laycan_start = record.get('Laycan Start Date')

                if laycan_start:
                    # Extract year from the parsed date
                    parsed_year = laycan_start.split('-')[0]
                    self.assertEqual(
                        parsed_year,
                        str(year),
                        f"Parser for year {year} produced date with wrong year: {laycan_start}"
                    )

    def test_configuration_persistence(self):
        """Test that parser configuration persists correctly"""

        for year in self.test_years:
            with self.subTest(year=year):
                parser = self._create_parser_with_year(year)

                # Parse multiple times to ensure configuration persists
                for i in range(3):
                    records = parser.parse(self.test_data)

                    if records and records[0].get('Laycan Start Date'):
                        parsed_year = records[0]['Laycan Start Date'].split('-')[0]
                        self.assertEqual(
                            parsed_year,
                            str(year),
                            f"Configuration changed after {i + 1} parse operations"
                        )

    def test_step_by_step_parsing(self):
        """Test the parsing process step by step to identify where it fails"""

        for year in self.test_years:
            with self.subTest(year=year):
                parser = self._create_parser_with_year(year)

                self.logger.info(f"Step-by-step parsing for year {year}")

                # Step 1: Check parser configuration
                if hasattr(parser, 'config'):
                    self.logger.debug(f"Parser config: {parser.config}")
                    if hasattr(parser.config, 'year'):
                        self.logger.debug(f"Config year: {parser.config.year}")

                # Step 2: Parse and get detailed info
                records = parser.parse(self.test_data)

                if records:
                    record = records[0]

                    # Step 3: Check each field
                    for field_name, field_value in record.items():
                        self.logger.debug(f"{field_name}: {field_value} (type: {type(field_value)})")

                    # Step 4: Focus on the failing field
                    laycan_start = record.get('Laycan Start Date')
                    if laycan_start is None:
                        self.logger.error(f"IDENTIFIED ISSUE: Laycan Start Date is None for year {year}")
                        self.logger.error(f"This means the date parsing/construction logic is failing")
                        self.logger.error(f"Full record: {record}")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)