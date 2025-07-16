#!/usr/bin/env python3
"""
Integration tests for the shipping data parser system.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from models import ShippingRecord
from config import AppConfig, ParserConfig
from shipping_parser import ShippingDataParser
from cli import (
    ShippingDataCLI, ShippingDataProcessor,
    FileDataReader, ExcelDataWriter, CLIFactory
)


class TestParserIntegration(unittest.TestCase):
    """Integration tests for the complete parser system."""

    def setUp(self):
        """Set up test fixtures."""
        self.app_config = AppConfig(default_year=2024)
        self.parser_config = ParserConfig()
        self.parser = ShippingDataParser(self.app_config, self.parser_config)

    def test_end_to_end_parsing_real_data(self):
        """Test complete parsing flow with real shipping data."""
        # Real shipping data from the original requirements
        real_data = """Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova
P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum
Sheng Hang Hua 13  5ktpns RPKO  LBK  / Zhapu   Usd 40 pmt  4-10 July  First Resources
Goldstar Shine  3ktons RPKO  PGG / Zhangjiagnag  hih 40ies  1H July   Alpha star
MOL TBN  17ktons UCO  PKL  / USG    USD 130 pmt  2H July   St, Bernards Resources"""

        # Parse the data
        records = self.parser.parse_shipping_data(real_data)

        # Verify results
        self.assertEqual(len(records), 5)

        # Check first record (standard format)
        record1 = records[0]
        self.assertEqual(record1['Vessel Name'], 'Dai Thanh')
        self.assertEqual(record1['Cargo'], 'POP')
        self.assertEqual(record1['Quantity (MT)'], 12000.0)
        self.assertEqual(record1['Charterer'], 'Nova')
        self.assertEqual(record1['Total Freight (USD)'], 348000.0)

        # Check second record (charterer-led format)
        record2 = records[1]
        self.assertEqual(record2['Charterer'], 'P66')
        self.assertEqual(record2['Vessel Name'], 'Seaways Moment')
        self.assertEqual(record2['Cargo'], 'UCO + Tallow')
        self.assertEqual(record2['Quantity (MT)'], 32000.0)
        self.assertEqual(record2['Total Freight (USD)'], 2150000.0)

        # Check third record (ktpns typo)
        record3 = records[2]
        self.assertEqual(record3['Vessel Name'], 'Sheng Hang Hua 13')
        self.assertEqual(record3['Cargo'], 'RPKO')
        self.assertEqual(record3['Quantity (MT)'], 5000.0)  # ktpns converted
        self.assertEqual(record3['Charterer'], 'First Resources')

        # Check fourth record (freight typo)
        record4 = records[3]
        self.assertEqual(record4['Vessel Name'], 'Goldstar Shine')
        self.assertEqual(record4['Freight'], 'hih 40ies')  # Preserved
        self.assertEqual(record4['Total Freight (USD)'], 120000.0)  # Calculated correctly

        # Check fifth record (complex vessel name)
        record5 = records[4]
        self.assertEqual(record5['Vessel Name'], 'MOL TBN')
        self.assertEqual(record5['Cargo'], 'UCO')
        self.assertEqual(record5['Charterer'], 'St, Bernards Resources')

    def test_save_and_load_excel_integration(self):
        """Test complete save and load Excel functionality."""
        # Test data
        test_data = """Sea Gull 18   12ktons POP Kumai / China   Usd 30 pmt bss sth  Ely Jun  Olam
Alfred N 23500 Mtons POME/Palms/UCO    China + Starits / Italy    Usd 2.85 M 1/1   2h June  ENI"""

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_output.xlsx"

            # Parse data
            records = self.parser.parse_shipping_data(test_data)
            self.assertEqual(len(records), 2)

            # Save to Excel
            success = self.parser.save_to_excel(records, str(output_file))
            self.assertTrue(success)
            self.assertTrue(output_file.exists())

            # Load and verify Excel content
            df = pd.read_excel(output_file, engine='openpyxl')
            self.assertEqual(len(df), 2)

            # Check column names
            expected_columns = [
                "Vessel Name", "Cargo", "Quantity (MT)", "Load Port", "Discharge Port",
                "Laycan", "Laycan Start Date", "Laycan End Date", "Freight",
                "Total Freight (USD)", "Charterer"
            ]
            for col in expected_columns:
                self.assertIn(col, df.columns)

            # Check data integrity
            self.assertEqual(df.iloc[0]['Vessel Name'], 'Sea Gull 18')
            self.assertEqual(df.iloc[1]['Vessel Name'], 'Alfred N')
            self.assertEqual(df.iloc[0]['Quantity (MT)'], 12000.0)
            self.assertEqual(df.iloc[1]['Quantity (MT)'], 23500.0)

    def test_configuration_effects_on_parsing(self):
        """Test how different configurations affect parsing behavior."""
        test_data = "vessel 10ktons cargo port1 / port2 YUsd 50 pmt 1-5 Jul charterer"

        # Test with typo correction enabled
        config_with_typos = AppConfig(enable_typo_correction=True)
        parser_with_typos = ShippingDataParser(config_with_typos, self.parser_config)
        records_with_correction = parser_with_typos.parse_shipping_data(test_data)

        # Test with typo correction disabled
        config_without_typos = AppConfig(enable_typo_correction=False)
        parser_without_typos = ShippingDataParser(config_without_typos, self.parser_config)
        records_without_correction = parser_without_typos.parse_shipping_data(test_data)

        # Both should parse the record
        self.assertEqual(len(records_with_correction), 1)
        self.assertEqual(len(records_without_correction), 1)

        # Freight calculation should work in both cases (number extraction still works)
        self.assertIsInstance(records_with_correction[0]['Total Freight (USD)'], float)
        self.assertIsInstance(records_without_correction[0]['Total Freight (USD)'], float)

    def test_year_configuration_effects(self):
        """Test how year configuration affects date parsing - FIXED VERSION"""

        test_data = "VESSEL 25-28 JUNE CARGO FROM PORT TO PORT2"
        years = [2023, 2024, 2025]

        for year in years:
            with self.subTest(year=year):
                print(f"\n🧪 Testing year {year}")

                # Create configuration
                config = ParserConfig()
                config.year = year
                config.default_year = year

                # Create parser
                parser = ShippingDataParser(config)

                # Use the CORRECT method name
                records = parser.parse_shipping_data(test_data)  # FIXED: was parser.parse()

                print(f"✅ Parsed {len(records)} records for year {year}")
                self.assertGreater(len(records), 0, f"No records parsed for year {year}")

                record = records[0]

                # Convert to dict if it's a ShippingRecord object
                if hasattr(record, 'to_dict'):
                    record_dict = record.to_dict()
                else:
                    record_dict = record

                print(f"📋 Record: {record_dict}")

                # Check the laycan start date
                laycan_start = record_dict.get('Laycan Start Date')
                print(f"📅 Laycan Start: {laycan_start}")

                # Enhanced assertion
                self.assertIsNotNone(
                    laycan_start,
                    f"Laycan Start Date is None for year {year}. Full record: {record_dict}"
                )

                expected_start_date = f'{year}-06-25'
                self.assertEqual(
                    laycan_start,
                    expected_start_date,
                    f"Expected '{expected_start_date}' but got '{laycan_start}' for year {year}"
                )

    def test_custom_charterer_configuration(self):
        """Test adding custom charterers to configuration."""
        test_data = "vessel 10ktons cargo port1 / port2 Usd 30 pmt 1-5 Jul CustomCharterer"

        # First, verify custom charterer is not recognized by default
        records_default = self.parser.parse_shipping_data(test_data)
        self.assertEqual(records_default[0]['Charterer'], 'N/A')

        # Add custom charterer and test
        custom_config = ParserConfig()
        custom_config.add_charterer("CustomCharterer")
        parser_custom = ShippingDataParser(self.app_config, custom_config)

        records_custom = parser_custom.parse_shipping_data(test_data)
        self.assertEqual(records_custom[0]['Charterer'], 'CustomCharterer')

    def test_custom_cargo_pattern_configuration(self):
        """Test adding custom cargo patterns to configuration."""
        test_data = "vessel 10ktons NewCargoType port1 / port2 Usd 30 pmt 1-5 Jul charterer"

        # First, verify custom cargo is not recognized by default
        records_default = self.parser.parse_shipping_data(test_data)
        # Should extract as generic cargo before port separator
        self.assertEqual(records_default[0]['Cargo'], 'NewCargoType')

        # Add custom cargo pattern and test
        custom_config = ParserConfig()
        custom_config.add_cargo_pattern(r'NewCargoType')
        parser_custom = ShippingDataParser(self.app_config, custom_config)

        records_custom = parser_custom.parse_shipping_data(test_data)
        self.assertEqual(records_custom[0]['Cargo'], 'NewCargoType')


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for the CLI system."""

    def test_file_to_excel_complete_flow(self):
        """Test complete flow from file input to Excel output."""
        # Prepare test data
        test_data = """Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar
Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova
P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum"""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create input file
            input_file = Path(temp_dir) / "input.txt"
            input_file.write_text(test_data)

            output_file = Path(temp_dir) / "output.xlsx"

            # Create CLI and process
            cli = CLIFactory.create_file_cli(str(input_file), str(output_file))

            # Mock print to suppress output during test
            with patch('builtins.print'):
                cli.run()

            # Verify output file was created
            self.assertTrue(output_file.exists())

            # Verify output content
            df = pd.read_excel(output_file, engine='openpyxl')
            self.assertEqual(len(df), 3)

            # Check some key values
            vessels = df['Vessel Name'].tolist()
            expected_vessels = ['Seagull 09', 'Dai Thanh', 'Seaways Moment']
            self.assertEqual(vessels, expected_vessels)

    def test_processor_integration_with_real_parser(self):
        """Test processor with real parser integration."""
        # Create real components
        app_config = AppConfig(default_year=2024)
        parser_config = ParserConfig()
        real_parser = ShippingDataParser(app_config, parser_config)
        processor = ShippingDataProcessor(real_parser)

        # Test data
        test_data = """Golden Violet 18ktons Palm oil   Padfng / WC India – Pakistan  Usd hi 30ies  mid Jul  Nova
Fauskanger 42ktons Biofeedstocks/chems  Chian / ARA   USd lo 3 M 4/1  10-20 July  Kolmar"""

        # Process data
        records = processor.process_data(test_data)

        # Verify processing
        self.assertEqual(len(records), 2)

        # Get summary
        summary = processor.get_summary(records)
        self.assertEqual(summary['total_records'], 2)
        self.assertGreater(summary['complete_records'], 0)
        self.assertGreaterEqual(summary['completion_rate'], 0.0)
        self.assertLessEqual(summary['completion_rate'], 1.0)

    def test_data_reader_writer_integration(self):
        """Test data reader and writer integration."""
        test_data = "vessel 15ktons cargo port1 / port2 Usd 45 pmt 1-10 Jul charterer"

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.txt"
            output_file = Path(temp_dir) / "output.xlsx"

            # Write test data
            input_file.write_text(test_data)

            # Create components
            app_config = AppConfig()
            parser_config = ParserConfig()
            parser = ShippingDataParser(app_config, parser_config)

            reader = FileDataReader(str(input_file))
            writer = ExcelDataWriter(parser)

            # Read data
            raw_data = reader.read_data()
            self.assertEqual(raw_data, test_data)

            # Parse data
            records = parser.parse_shipping_data(raw_data)
            self.assertEqual(len(records), 1)

            # Write data
            success = writer.write_data(records, str(output_file))
            self.assertTrue(success)
            self.assertTrue(output_file.exists())

    def test_cli_error_handling_integration(self):
        """Test CLI error handling in integration scenarios."""
        # Test with non-existent input file
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_file = Path(temp_dir) / "nonexistent.txt"

            cli = CLIFactory.create_file_cli(str(non_existent_file))

            # Should handle FileNotFoundError gracefully
            with patch('builtins.print'), patch('sys.exit') as mock_exit:
                cli.run()
                mock_exit.assert_called_once_with(2)  # File error exit code

    def test_configuration_validation_integration(self):
        """Test configuration validation in integration context."""
        # Test invalid configuration
        invalid_config = AppConfig(
            default_year=1999,  # Too old
            log_level="INVALID",  # Invalid log level
            output_filename="test.txt"  # Wrong extension
        )

        with self.assertRaises(ValueError):
            invalid_config.validate()

        # Test valid configuration
        valid_config = AppConfig(
            default_year=2024,
            log_level="DEBUG",
            output_filename="test.xlsx"
        )

        # Should not raise any exception
        valid_config.validate()


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world usage scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.app_config = AppConfig(default_year=2024)
        self.parser_config = ParserConfig()
        self.parser = ShippingDataParser(self.app_config, self.parser_config)

    def test_mixed_format_data(self):
        """Test parsing data with mixed standard and charterer-led formats."""
        mixed_data = """Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar
P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum
Alfred N 23500 Mtons POME/Palms/UCO    China + Starits / Italy    Usd 2.85 M 1/1   2h June  ENI
Neste / Baltic Pioneer / 45,000MT UCOME / Rotterdam to New York / 15-25 July / USD 3.2M Lumpsum"""

        records = self.parser.parse_shipping_data(mixed_data)

        # Should parse all records
        self.assertEqual(len(records), 4)

        # Verify mixed formats are handled correctly
        charterers = [record['Charterer'] for record in records]
        self.assertIn('Wilmar', charterers)  # Standard format
        self.assertIn('P66', charterers)  # Charterer-led format
        self.assertIn('ENI', charterers)  # Standard format
        self.assertIn('Neste', charterers)  # Charterer-led format

    def test_data_with_various_typos(self):
        """Test parsing data with multiple types of typos."""
        typo_data = """Sheng Hang Hua 13  5ktpns RPKO  LBK  / Zhapu   Usd 40 pmt  4-10 July  First Resources
Goldstar Shine  3ktons RPKO  PGG / Zhangjiagnag  hih 40ies  1H July   Alpha star
SC Hong Kong  8500 Mtons POP  Straits  / Kandla + Port Qasim  YUsd 55 pmt 1-2  ely July  Unilever
Maritime Tbn  30ktons Palms    Straits  / WC India   Usd 30 pmt 1 H Jul   Olam"""

        records = self.parser.parse_shipping_data(typo_data)

        # Should parse all records despite typos
        self.assertEqual(len(records), 4)

        # Check that freight calculations work despite typos
        freight_values = [record['Total Freight (USD)'] for record in records]
        numeric_freights = [f for f in freight_values if isinstance(f, (int, float))]
        self.assertGreater(len(numeric_freights), 0)  # At least some should calculate

    def test_large_dataset_performance(self):
        """Test parser performance with larger dataset."""
        # Create a larger dataset by repeating and varying base records
        base_records = [
            "Vessel1 10ktons POP Port1 / Port2 Usd 30 pmt 1-5 Jan Charterer1",
            "Vessel2 15ktons UCO Port3 / Port4 Usd 45 pmt 6-10 Feb Charterer2",
            "Charterer3 / Vessel3 / 20,000MT Palm oil / Port5 to Port6 / 11-15 Mar / USD 1.5M Lumpsum",
        ]

        # Create 100 records with variations
        large_dataset = []
        for i in range(100):
            base_record = base_records[i % len(base_records)]
            # Add variation by changing numbers
            varied_record = base_record.replace("Vessel", f"Vessel{i}").replace("Port", f"Port{i}")
            large_dataset.append(varied_record)

        large_data = '\n'.join(large_dataset)

        # Parse large dataset
        import time
        start_time = time.time()
        records = self.parser.parse_shipping_data(large_data)
        end_time = time.time()

        # Verify results
        self.assertEqual(len(records), 100)

        # Performance check (should complete in reasonable time)
        parse_time = end_time - start_time
        self.assertLess(parse_time, 5.0)  # Should complete within 5 seconds

    def test_incomplete_data_handling(self):
        """Test handling of incomplete or malformed records."""
        incomplete_data = """Complete Vessel 10ktons POP Port1 / Port2 Usd 30 pmt 1-5 Jul Charterer
Incomplete Vessel   # Missing quantity and other info
Another Vessel ktons  # Invalid quantity
    # Empty line
Just Some Random Text That Doesn't Match Any Pattern
Partial Vessel 15ktons   # Missing cargo and ports
Final Vessel 20ktons Cargo Port1 / Port2   # Missing freight and charterer"""

        records = self.parser.parse_shipping_data(incomplete_data)

        # Should extract what it can from valid records
        self.assertGreater(len(records), 0)
        self.assertLessEqual(len(records), 7)  # May parse all lines with partial data

        # Check that complete record is properly parsed
        complete_records = [r for r in records if r['Vessel Name'] == 'Complete Vessel']
        self.assertEqual(len(complete_records), 1)
        complete_record = complete_records[0]
        self.assertEqual(complete_record['Quantity (MT)'], 10000.0)
        self.assertEqual(complete_record['Cargo'], 'POP')

        # Check that at least some records have incomplete data (showing parser robustness)
        incomplete_records = [r for r in records if r['Quantity (MT)'] == 'N/A' or r['Cargo'] == 'N/A']
        self.assertGreater(len(incomplete_records), 0)  # Some should be incomplete

    def test_edge_case_dates_and_freight(self):
        """Test edge cases in date and freight parsing."""
        edge_case_data = """Vessel1 10ktons Cargo Port1 / Port2 Usd 0 pmt 1-31 Dec TestCharterer
Vessel2 15ktons Cargo Port3 / Port4 USD 999.99M Lumpsum 31 Dec – 1 Jan NextCharterer
Vessel3 20ktons Cargo Port5 / Port6 RNR invalid date format AnotherCharterer"""

        records = self.parser.parse_shipping_data(edge_case_data)

        # Should handle edge cases gracefully
        self.assertGreater(len(records), 0)

        # Check specific edge cases
        for record in records:
            # Freight should be either a number or "N/A"
            freight = record['Total Freight (USD)']
            self.assertTrue(isinstance(freight, (int, float)) or freight == "N/A")

            # Dates should be valid format or None
            start_date = record['Laycan Start Date']
            if start_date is not None:
                # Should be valid date string
                self.assertRegex(start_date, r'\d{4}-\d{2}-\d{2}')


if __name__ == '__main__':
    # Run integration tests with detailed output
    unittest.main(verbosity=2)