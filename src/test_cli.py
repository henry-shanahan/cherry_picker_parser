#!/usr/bin/env python3
"""
Unit tests for CLI components.
"""

import unittest
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from config import AppConfig, ParserConfig
from cli import (
    StdinDataReader, FileDataReader, ExcelDataWriter,
    ShippingDataProcessor, ShippingDataCLI, CLIFactory,
    create_argument_parser, main
)


class TestDataReaders(unittest.TestCase):
    """Test data input classes."""

    def test_file_data_reader_success(self):
        """Test successful file reading."""
        test_content = "test shipping data"

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            reader = FileDataReader(temp_path)
            result = reader.read_data()
            self.assertEqual(result, test_content)
        finally:
            Path(temp_path).unlink()

    def test_file_data_reader_missing_file(self):
        """Test reading non-existent file raises appropriate error."""
        reader = FileDataReader("nonexistent_file.txt")

        with self.assertRaises(FileNotFoundError) as cm:
            reader.read_data()

        self.assertIn("Input file not found", str(cm.exception))

    def test_file_data_reader_permission_error(self):
        """Test handling of permission errors when reading file."""
        # Create a file and make it unreadable
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test")
            temp_path = f.name

        try:
            # Make file unreadable (on Unix systems)
            if hasattr(Path, 'chmod'):
                Path(temp_path).chmod(0o000)

                reader = FileDataReader(temp_path)
                with self.assertRaises(RuntimeError) as cm:
                    reader.read_data()

                self.assertIn("Failed to read file", str(cm.exception))
        finally:
            # Restore permissions and delete
            if hasattr(Path, 'chmod'):
                Path(temp_path).chmod(0o644)
            Path(temp_path).unlink(missing_ok=True)

    @patch('sys.stdin')
    def test_stdin_data_reader_success(self, mock_stdin):
        """Test successful stdin reading."""
        test_data = "pasted shipping data"
        mock_stdin.read.return_value = test_data

        reader = StdinDataReader("Test prompt")
        result = reader.read_data()

        self.assertEqual(result, test_data)
        mock_stdin.read.assert_called_once()

    @patch('sys.stdin')
    @patch('sys.exit')
    @patch('builtins.print')
    def test_stdin_data_reader_keyboard_interrupt(self, mock_print, mock_exit, mock_stdin):
        """Test handling keyboard interrupt gracefully."""
        mock_stdin.read.side_effect = KeyboardInterrupt()

        reader = StdinDataReader()
        reader.read_data()

        mock_exit.assert_called_once_with(0)
        # Should print cancellation message
        self.assertTrue(any("cancelled" in str(call) for call in mock_print.call_args_list))

    @patch('sys.stdin')
    def test_stdin_data_reader_runtime_error(self, mock_stdin):
        """Test handling of runtime errors during stdin reading."""
        mock_stdin.read.side_effect = IOError("Stdin error")

        reader = StdinDataReader()

        with self.assertRaises(RuntimeError) as cm:
            reader.read_data()

        self.assertIn("Failed to read input", str(cm.exception))

    def test_stdin_data_reader_custom_prompt(self):
        """Test stdin reader with custom prompt message."""
        custom_prompt = "Custom prompt message"
        reader = StdinDataReader(custom_prompt)

        self.assertEqual(reader.prompt_message, custom_prompt)


class TestDataWriters(unittest.TestCase):
    """Test data output classes."""

    def test_excel_writer_success(self):
        """Test successful Excel writing."""
        mock_parser = Mock()
        mock_parser.save_to_excel.return_value = True

        writer = ExcelDataWriter(mock_parser)
        records = [{'Vessel Name': 'Test', 'Cargo': 'Test Cargo'}]
        filename = "test.xlsx"

        result = writer.write_data(records, filename)

        self.assertTrue(result)
        mock_parser.save_to_excel.assert_called_once_with(records, filename)

    def test_excel_writer_failure(self):
        """Test Excel writing failure."""
        mock_parser = Mock()
        mock_parser.save_to_excel.return_value = False

        writer = ExcelDataWriter(mock_parser)
        result = writer.write_data([], "test.xlsx")

        self.assertFalse(result)


class TestShippingDataProcessor(unittest.TestCase):
    """Test the core business logic processor."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_parser = Mock()
        self.processor = ShippingDataProcessor(self.mock_parser)

    def test_process_data_success(self):
        """Test successful data processing."""
        raw_data = "test shipping data"
        expected_records = [{'Vessel Name': 'Test Vessel', 'Cargo': 'Test Cargo'}]

        self.mock_parser.parse_shipping_data.return_value = expected_records

        result = self.processor.process_data(raw_data)

        self.assertEqual(result, expected_records)
        self.mock_parser.parse_shipping_data.assert_called_once_with(raw_data)

    def test_process_data_empty_input(self):
        """Test processing empty input raises appropriate error."""
        test_cases = ["", "   ", "\n\n", None]

        for empty_input in test_cases:
            with self.subTest(input=empty_input):
                with self.assertRaises(ValueError) as cm:
                    self.processor.process_data(empty_input or "")

                self.assertIn("No data provided", str(cm.exception))

    def test_process_data_no_records_parsed(self):
        """Test processing data that yields no records."""
        self.mock_parser.parse_shipping_data.return_value = []

        with self.assertRaises(ValueError) as cm:
            self.processor.process_data("invalid data")

        self.assertIn("No valid records", str(cm.exception))

    def test_get_summary_comprehensive(self):
        """Test comprehensive summary generation."""
        test_records = [
            {
                'Vessel Name': 'Complete Ship',
                'Quantity (MT)': 1000.0,
                'Laycan Start Date': '2024-01-01',
                'Total Freight (USD)': 50000.0
            },
            {
                'Vessel Name': 'N/A',  # Incomplete - no vessel name
                'Quantity (MT)': 2000.0,
                'Laycan Start Date': None,  # No laycan
                'Total Freight (USD)': 'N/A'  # No freight
            },
            {
                'Vessel Name': 'Partial Ship',
                'Quantity (MT)': 'N/A',  # Incomplete - no quantity
                'Laycan Start Date': '2024-01-02',
                'Total Freight (USD)': 75000.0
            },
            {
                'Vessel Name': 'Another Ship',
                'Quantity (MT)': 3000.0,
                'Laycan Start Date': '2024-01-03',
                'Total Freight (USD)': 'N/A'  # No freight calculation
            }
        ]

        summary = self.processor.get_summary(test_records)

        expected = {
            'total_records': 4,
            'complete_records': 2,  # Complete Ship and Another Ship
            'laycan_records': 3,  # All except second record
            'freight_records': 2,  # Complete Ship and Partial Ship
            'completion_rate': 0.5  # 2/4 = 50%
        }

        self.assertEqual(summary, expected)

    def test_get_summary_empty_records(self):
        """Test summary generation with empty records list."""
        summary = self.processor.get_summary([])

        expected = {
            'total_records': 0,
            'complete_records': 0,
            'laycan_records': 0,
            'freight_records': 0,
            'completion_rate': 0
        }

        self.assertEqual(summary, expected)

    def test_get_summary_all_complete_records(self):
        """Test summary generation with all complete records."""
        test_records = [
            {
                'Vessel Name': 'Ship1',
                'Quantity (MT)': 1000.0,
                'Laycan Start Date': '2024-01-01',
                'Total Freight (USD)': 50000.0
            },
            {
                'Vessel Name': 'Ship2',
                'Quantity (MT)': 2000.0,
                'Laycan Start Date': '2024-01-02',
                'Total Freight (USD)': 100000.0
            }
        ]

        summary = self.processor.get_summary(test_records)

        self.assertEqual(summary['completion_rate'], 1.0)  # 100%
        self.assertEqual(summary['total_records'], 2)
        self.assertEqual(summary['complete_records'], 2)


class TestShippingDataCLI(unittest.TestCase):
    """Test the CLI application."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = AppConfig(output_filename="test_output.xlsx")
        self.mock_reader = Mock()
        self.mock_writer = Mock()
        self.mock_processor = Mock()

        self.cli = ShippingDataCLI(
            self.config, self.mock_reader, self.mock_writer, self.mock_processor
        )

    @patch('builtins.print')
    def test_run_success_full_flow(self, mock_print):
        """Test successful CLI execution with full flow."""
        # Arrange
        test_data = "test shipping data"
        test_records = [{'Vessel Name': 'Test', 'Cargo': 'Test Cargo'}]
        test_summary = {
            'total_records': 1,
            'complete_records': 1,
            'laycan_records': 0,
            'freight_records': 0,
            'completion_rate': 1.0
        }

        self.mock_reader.read_data.return_value = test_data
        self.mock_processor.process_data.return_value = test_records
        self.mock_writer.write_data.return_value = True
        self.mock_processor.get_summary.return_value = test_summary

        # Act
        self.cli.run()

        # Assert
        self.mock_reader.read_data.assert_called_once()
        self.mock_processor.process_data.assert_called_once_with(test_data)
        self.mock_writer.write_data.assert_called_once_with(test_records, "test_output.xlsx")
        self.mock_processor.get_summary.assert_called_once_with(test_records)

        # Verify output was printed
        self.assertTrue(mock_print.called)
        print_calls = [str(call) for call in mock_print.call_args_list]

        # Check for expected output messages
        output_text = ' '.join(print_calls)
        self.assertIn("Shipping Data Parsing Tool", output_text)
        self.assertIn("Process complete", output_text)
        self.assertIn("Total records: 1", output_text)

    @patch('builtins.print')
    @patch('sys.exit')
    def test_run_validation_error(self, mock_exit, mock_print):
        """Test CLI handling of validation errors."""
        self.mock_reader.read_data.return_value = ""  # Empty input

        self.cli.run()

        mock_exit.assert_called_once_with(1)

        # Verify error message was printed
        error_calls = [call for call in mock_print.call_args_list if '❌' in str(call)]
        self.assertTrue(len(error_calls) > 0)

    @patch('builtins.print')
    @patch('sys.exit')
    def test_run_file_not_found_error(self, mock_exit, mock_print):
        """Test CLI handling of file not found errors."""
        self.mock_reader.read_data.side_effect = FileNotFoundError("File not found")

        self.cli.run()

        mock_exit.assert_called_once_with(2)

    @patch('builtins.print')
    @patch('sys.exit')
    def test_run_runtime_error(self, mock_exit, mock_print):
        """Test CLI handling of runtime errors."""
        self.mock_reader.read_data.return_value = "test data"
        self.mock_processor.process_data.side_effect = RuntimeError("Processing failed")

        self.cli.run()

        mock_exit.assert_called_once_with(3)

    @patch('builtins.print')
    @patch('sys.exit')
    def test_run_unexpected_error(self, mock_exit, mock_print):
        """Test CLI handling of unexpected errors."""
        self.mock_reader.read_data.side_effect = Exception("Unexpected error")

        self.cli.run()

        mock_exit.assert_called_once_with(99)

    @patch('builtins.print')
    @patch('sys.exit')
    def test_run_save_failure(self, mock_exit, mock_print):
        """Test CLI handling of save failures."""
        self.mock_reader.read_data.return_value = "test data"
        self.mock_processor.process_data.return_value = [{'test': 'record'}]
        self.mock_writer.write_data.return_value = False  # Save failure

        self.cli.run()

        mock_exit.assert_called_once_with(3)  # Runtime error


class TestCLIFactory(unittest.TestCase):
    """Test the CLI factory class."""

    @patch('cli.ShippingDataParser')
    def test_create_stdin_cli(self, mock_parser_class):
        """Test creating stdin CLI with default configuration."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        cli = CLIFactory.create_stdin_cli()

        self.assertIsInstance(cli, ShippingDataCLI)
        self.assertIsInstance(cli.data_reader, StdinDataReader)
        self.assertIsInstance(cli.data_writer, ExcelDataWriter)
        self.assertIsInstance(cli.processor, ShippingDataProcessor)

        # Verify parser was created with correct configuration
        mock_parser_class.assert_called_once()

    @patch('cli.ShippingDataParser')
    def test_create_stdin_cli_custom_config(self, mock_parser_class):
        """Test creating stdin CLI with custom configuration."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        custom_app_config = AppConfig(output_filename="custom.xlsx", default_year=2023)
        custom_parser_config = ParserConfig()

        cli = CLIFactory.create_stdin_cli(custom_app_config, custom_parser_config)

        self.assertEqual(cli.config.output_filename, "custom.xlsx")
        self.assertEqual(cli.config.default_year, 2023)

    @patch('cli.ShippingDataParser')
    def test_create_file_cli(self, mock_parser_class):
        """Test creating file-based CLI."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        with tempfile.NamedTemporaryFile() as temp_file:
            cli = CLIFactory.create_file_cli(temp_file.name, "output.xlsx")

            self.assertIsInstance(cli, ShippingDataCLI)
            self.assertIsInstance(cli.data_reader, FileDataReader)
            self.assertEqual(cli.config.output_filename, "output.xlsx")

    @patch('cli.AppConfig.from_env')
    @patch('cli.ShippingDataParser')
    def test_create_from_env(self, mock_parser_class, mock_config_from_env):
        """Test creating CLI from environment variables."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        mock_env_config = AppConfig(output_filename="env.xlsx")
        mock_config_from_env.return_value = mock_env_config

        cli = CLIFactory.create_from_env()

        self.assertIsInstance(cli, ShippingDataCLI)
        mock_config_from_env.assert_called_once()


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing."""

    def test_create_argument_parser(self):
        """Test argument parser creation."""
        parser = create_argument_parser()

        # Test that parser is created successfully
        self.assertIsNotNone(parser)

        # Test help text generation doesn't crash
        help_text = parser.format_help()
        self.assertIn("shipping data", help_text.lower())

    def test_parse_arguments_defaults(self):
        """Test parsing with default arguments."""
        parser = create_argument_parser()

        # Test default arguments (empty)
        args = parser.parse_args([])

        self.assertIsNone(args.input)
        self.assertEqual(args.output, 'parsed_shipping_data.xlsx')
        self.assertIsNone(args.year)
        self.assertEqual(args.log_level, 'INFO')
        self.assertFalse(args.no_typo_correction)
        self.assertFalse(args.no_freight_calculation)

    def test_parse_arguments_all_options(self):
        """Test parsing with all options specified."""
        parser = create_argument_parser()

        args = parser.parse_args([
            '-i', 'input.txt',
            '-o', 'output.xlsx',
            '--year', '2023',
            '--log-level', 'DEBUG',
            '--no-typo-correction',
            '--no-freight-calculation'
        ])

        self.assertEqual(args.input, 'input.txt')
        self.assertEqual(args.output, 'output.xlsx')
        self.assertEqual(args.year, 2023)
        self.assertEqual(args.log_level, 'DEBUG')
        self.assertTrue(args.no_typo_correction)
        self.assertTrue(args.no_freight_calculation)

    def test_parse_arguments_invalid_log_level(self):
        """Test parsing with invalid log level."""
        parser = create_argument_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(['--log-level', 'INVALID'])

    def test_parse_arguments_invalid_year(self):
        """Test parsing with invalid year."""
        parser = create_argument_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(['--year', 'invalid'])


class TestMainFunction(unittest.TestCase):
    """Test the main function integration."""

    @patch('cli.CLIFactory.create_stdin_cli')
    @patch('sys.argv', ['prog'])
    def test_main_stdin_mode(self, mock_create_cli):
        """Test main function in stdin mode."""
        mock_cli = Mock()
        mock_create_cli.return_value = mock_cli

        main()

        mock_create_cli.assert_called_once()
        mock_cli.run.assert_called_once()

    @patch('cli.CLIFactory.create_file_cli')
    @patch('sys.argv', ['prog', '-i', 'input.txt'])
    def test_main_file_mode(self, mock_create_cli):
        """Test main function in file mode."""
        mock_cli = Mock()
        mock_create_cli.return_value = mock_cli

        main()

        mock_create_cli.assert_called_once()
        mock_cli.run.assert_called_once()

    @patch('builtins.print')
    @patch('sys.exit')
    @patch('sys.argv', ['prog'])
    @patch('cli.CLIFactory.create_stdin_cli')
    def test_main_keyboard_interrupt(self, mock_create_cli, mock_exit, mock_print):
        """Test main function handling keyboard interrupt."""
        mock_cli = Mock()
        mock_cli.run.side_effect = KeyboardInterrupt()
        mock_create_cli.return_value = mock_cli

        main()

        mock_exit.assert_called_once_with(0)
        # Should print cancellation message
        cancel_calls = [call for call in mock_print.call_args_list if 'cancelled' in str(call)]
        self.assertTrue(len(cancel_calls) > 0)

    @patch('builtins.print')
    @patch('sys.exit')
    @patch('sys.argv', ['prog'])
    @patch('cli.CLIFactory.create_stdin_cli')
    def test_main_unexpected_exception(self, mock_create_cli, mock_exit, mock_print):
        """Test main function handling unexpected exceptions."""
        mock_cli = Mock()
        mock_cli.run.side_effect = Exception("Unexpected error")
        mock_create_cli.return_value = mock_cli

        main()

        mock_exit.assert_called_once_with(99)
        # Should print error message
        error_calls = [call for call in mock_print.call_args_list if 'Fatal error' in str(call)]
        self.assertTrue(len(error_calls) > 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)