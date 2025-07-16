#!/usr/bin/env python3
"""
Command-line interface for shipping data parsing.
"""

import os
import sys
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Protocol, Optional
import argparse

from models import ShippingRecord
from config import AppConfig, ParserConfig
from shipping_parser import ShippingDataParser

logger = logging.getLogger(__name__)


# ============ PROTOCOLS & INTERFACES ============

class DataReader(Protocol):
    """Protocol for reading input data."""
    def read_data(self) -> str:
        """Read and return input data."""
        ...


class DataWriter(Protocol):
    """Protocol for writing output data."""
    def write_data(self, records: List[Dict], filename: str) -> bool:
        """Write records to output format."""
        ...


class ShippingParserProtocol(Protocol):
    """Protocol for parsing shipping data."""
    def parse_shipping_data(self, text_data: str) -> List[Dict]:
        """Parse raw text into structured records."""
        ...

    def save_to_excel(self, records: List[Dict], filename: str) -> bool:
        """Save records to Excel file."""
        ...


# ============ CONCRETE IMPLEMENTATIONS ============

class StdinDataReader:
    """Reads data from standard input."""

    def __init__(self, prompt_message: str = None):
        self.prompt_message = prompt_message

    def read_data(self) -> str:
        """Read multi-line data from stdin until EOF."""
        if self.prompt_message:
            print(self.prompt_message)

        try:
            return sys.stdin.read()
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            print("\n❌ Operation cancelled by user.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error reading from stdin: {e}")
            raise RuntimeError(f"Failed to read input: {e}")


class FileDataReader:
    """Reads data from a file."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)

    def read_data(self) -> str:
        """Read data from file."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"Input file not found: {self.filepath}")

        try:
            return self.filepath.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading file {self.filepath}: {e}")
            raise RuntimeError(f"Failed to read file {self.filepath}: {e}")


class ExcelDataWriter:
    """Writes data to Excel format using the parser."""

    def __init__(self, parser: ShippingParserProtocol):
        self.parser = parser

    def write_data(self, records: List[Dict], filename: str) -> bool:
        """Write records to Excel file."""
        return self.parser.save_to_excel(records, filename)


# ============ BUSINESS LOGIC ============

class ShippingDataProcessor:
    """Core business logic for processing shipping data."""

    def __init__(self, parser: ShippingParserProtocol):
        self.parser = parser

    def process_data(self, raw_data: str) -> List[Dict]:
        """Process raw data into structured records."""
        if not raw_data or not raw_data.strip():
            raise ValueError("No data provided")

        logger.info("Processing shipping data...")
        records = self.parser.parse_shipping_data(raw_data)

        if not records:
            raise ValueError("No valid records could be parsed from the input data")

        logger.info(f"Successfully processed {len(records)} records")
        return records

    def get_summary(self, records: List[Dict]) -> Dict:
        """Generate summary statistics for processed records."""
        total_records = len(records)

        complete_records = sum(
            1 for record in records
            if (record.get('Vessel Name', 'N/A') != 'N/A' and
                record.get('Quantity (MT)', 'N/A') != 'N/A' and
                isinstance(record.get('Quantity (MT)'), (int, float)))
        )

        laycan_records = sum(
            1 for record in records
            if record.get('Laycan Start Date') is not None
        )

        freight_records = sum(
            1 for record in records
            if (record.get('Total Freight (USD)', 'N/A') != 'N/A' and
                isinstance(record.get('Total Freight (USD)'), (int, float)))
        )

        return {
            'total_records': total_records,
            'complete_records': complete_records,
            'laycan_records': laycan_records,
            'freight_records': freight_records,
            'completion_rate': complete_records / total_records if total_records > 0 else 0
        }


# ============ CLI APPLICATION ============

class ShippingDataCLI:
    """Command-line interface for shipping data processing."""

    def __init__(
        self,
        config: AppConfig,
        data_reader: DataReader,
        data_writer: DataWriter,
        processor: ShippingDataProcessor
    ):
        self.config = config
        self.data_reader = data_reader
        self.data_writer = data_writer
        self.processor = processor

        # Configure logging
        self._configure_logging()

    def _configure_logging(self):
        """Configure logging based on config."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format=self.config.log_format
        )

    def run(self) -> None:
        """Run the CLI application."""
        try:
            self._print_header()

            # Read input
            raw_data = self._read_input()

            # Process data
            records = self._process_data(raw_data)

            # Save output
            self._save_output(records)

            # Show summary
            self._show_summary(records)

        except ValueError as e:
            self._handle_error(f"Validation error: {e}", exit_code=1)
        except FileNotFoundError as e:
            self._handle_error(f"File error: {e}", exit_code=2)
        except RuntimeError as e:
            self._handle_error(f"Runtime error: {e}", exit_code=3)
        except Exception as e:
            logger.exception("Unexpected error occurred")
            self._handle_error(f"Unexpected error: {e}", exit_code=99)

    def _print_header(self) -> None:
        """Print application header."""
        print("🚢 Shipping Data Parsing Tool")
        print("=" * 50)

    def _read_input(self) -> str:
        """Read and validate input data."""
        logger.info("Reading input data...")
        raw_data = self.data_reader.read_data()

        if not raw_data.strip():
            raise ValueError("No data was provided")

        logger.info(f"Read {len(raw_data)} characters of input data")
        return raw_data

    def _process_data(self, raw_data: str) -> List[Dict]:
        """Process the raw data."""
        logger.info("Parsing shipping data...")
        print("⚙️  Parsing the provided data...")
        return self.processor.process_data(raw_data)

    def _save_output(self, records: List[Dict]) -> None:
        """Save processed records to file."""
        print(f"💾 Saving data to '{self.config.output_filename}'...")
        logger.info(f"Saving {len(records)} records to {self.config.output_filename}")

        success = self.data_writer.write_data(records, self.config.output_filename)
        if not success:
            raise RuntimeError("Failed to save output file")

        logger.info("Output file saved successfully")

    def _show_summary(self, records: List[Dict]) -> None:
        """Display processing summary."""
        output_path = Path(self.config.output_filename).resolve()

        print("\n🎉 Process complete!")
        print(f"   File saved: {output_path}")

        summary = self.processor.get_summary(records)
        print(f"\n📊 Summary:")
        print(f"   - Total records: {summary['total_records']}")
        print(f"   - Complete records: {summary['complete_records']}")
        print(f"   - Records with laycan dates: {summary['laycan_records']}")
        print(f"   - Records with freight calculations: {summary['freight_records']}")
        print(f"   - Completion rate: {summary['completion_rate']:.1%}")

    def _handle_error(self, message: str, exit_code: int = 1) -> None:
        """Handle and log errors, then exit."""
        print(f"\n❌ {message}")
        logger.error(message)
        sys.exit(exit_code)


# ============ FACTORY & DEPENDENCY INJECTION ============

class CLIFactory:
    """Factory for creating CLI application with dependencies."""

    @staticmethod
    def create_stdin_cli(app_config: AppConfig = None, parser_config: ParserConfig = None) -> ShippingDataCLI:
        """Create CLI for stdin-based processing."""
        app_config = app_config or AppConfig()
        parser_config = parser_config or ParserConfig()

        # Validate configuration
        app_config.validate()

        # Create parser
        parser = ShippingDataParser(app_config, parser_config)

        # Create components
        data_reader = StdinDataReader(app_config.stdin_prompt_message)
        data_writer = ExcelDataWriter(parser)
        processor = ShippingDataProcessor(parser)

        return ShippingDataCLI(app_config, data_reader, data_writer, processor)

    @staticmethod
    def create_file_cli(
        input_file: str,
        output_file: str = None,
        app_config: AppConfig = None,
        parser_config: ParserConfig = None
    ) -> ShippingDataCLI:
        """Create CLI for file-based processing."""
        app_config = app_config or AppConfig()
        parser_config = parser_config or ParserConfig()

        if output_file:
            app_config.output_filename = output_file

        # Validate configuration
        app_config.validate()

        # Create parser
        parser = ShippingDataParser(app_config, parser_config)

        # Create components
        data_reader = FileDataReader(input_file)
        data_writer = ExcelDataWriter(parser)
        processor = ShippingDataProcessor(parser)

        return ShippingDataCLI(app_config, data_reader, data_writer, processor)

    @staticmethod
    def create_from_env() -> ShippingDataCLI:
        """Create CLI using environment variables for configuration."""
        app_config = AppConfig.from_env()
        parser_config = ParserConfig()
        return CLIFactory.create_stdin_cli(app_config, parser_config)


# ============ ARGUMENT PARSING ============

def create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse unstructured shipping data into structured Excel format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Read from stdin
  %(prog)s -i input.txt              # Read from file
  %(prog)s -i input.txt -o output.xlsx   # Read from file, custom output
  %(prog)s --year 2023               # Use 2023 as default year
  %(prog)s --log-level DEBUG         # Enable debug logging
        """
    )

    parser.add_argument(
        '-i', '--input',
        help='Input file path (if not provided, reads from stdin)'
    )

    parser.add_argument(
        '-o', '--output',
        default='parsed_shipping_data.xlsx',
        help='Output Excel file path (default: %(default)s)'
    )

    parser.add_argument(
        '--year',
        type=int,
        default=None,
        help='Default year for date parsing (default: current year)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: %(default)s)'
    )

    parser.add_argument(
        '--no-typo-correction',
        action='store_true',
        help='Disable automatic typo correction'
    )

    parser.add_argument(
        '--no-freight-calculation',
        action='store_true',
        help='Disable freight calculation'
    )

    return parser


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = create_argument_parser()
    return parser.parse_args()


# ============ MAIN ENTRY POINT ============

def main():
    """Main entry point for the CLI application."""
    try:
        args = parse_arguments()

        # Create configuration from arguments
        app_config = AppConfig(
            output_filename=args.output,
            default_year=args.year or AppConfig().default_year,
            log_level=args.log_level,
            enable_typo_correction=not args.no_typo_correction,
            enable_freight_calculation=not args.no_freight_calculation
        )

        parser_config = ParserConfig()

        # Create and run appropriate CLI
        if args.input:
            cli = CLIFactory.create_file_cli(args.input, args.output, app_config, parser_config)
        else:
            cli = CLIFactory.create_stdin_cli(app_config, parser_config)

        cli.run()

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error in main")
        sys.exit(99)


if __name__ == "__main__":
    main()