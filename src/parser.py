import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DateFormat(Enum):
    """Enum for supported date formats"""
    END_MONTH_TO_EARLY_MONTH = r'end\s+([a-zA-Z]+)\s*-\s*ely\s+([a-zA-Z]+)'
    DAY_RANGE_MONTH = r'(\d{1,2})-(\d{1,2})\s+([a-zA-Z]+)'
    SECOND_HALF_MONTH = r'2[Hh]\s+([a-zA-Z]+)'
    EARLY_MONTH = r'[Ee]arly\s+([a-zA-Z]+)'
    END_MONTH = r'[Ee]nd\s+([a-zA-Z]+)'


@dataclass
class ShippingRecord:
    """Data class for shipping records with proper typing"""
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper column names"""
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
            "Charterer": self.charterer
        }


class LaycanParser:
    """Handles laycan date parsing with proper error handling"""

    # Constants
    DAYS_OFFSET_END_MONTH = 6
    EARLY_MONTH_DAY = 10
    SECOND_HALF_START_DAY = 16

    def __init__(self, default_year: Optional[int] = None):
        # Use current year by default, but allow override for testing or historical data
        self.default_year = default_year or datetime.now().year

    def _get_month_number(self, month_str: str) -> int:
        """Convert month string to number"""
        return datetime.strptime(month_str[:3], "%b").month

    def _get_end_of_month(self, year: int, month: int) -> datetime:
        """Get the last day of a month"""
        return (datetime(year, month, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    def _adjust_year_for_cross_year_dates(self, start_date: datetime, end_date: datetime) -> datetime:
        """Adjust end date year if it's in the next year"""
        if end_date < start_date:
            return end_date.replace(year=end_date.year + 1)
        return end_date

    def _parse_end_month_to_early_month(self, month1_str: str, month2_str: str) -> Dict[str, Optional[str]]:
        """Parse format: 'end June - ely July'"""
        try:
            month1 = self._get_month_number(month1_str)
            month2 = self._get_month_number(month2_str)

            year1 = self._smart_year_detection(month1)
            year2 = self._smart_year_detection(month2)

            # If month2 < month1, it's likely next year
            if month2 < month1:
                year2 = year1 + 1

            end_of_month1 = self._get_end_of_month(year1, month1)
            start_date = end_of_month1 - timedelta(days=self.DAYS_OFFSET_END_MONTH)
            end_date = datetime(year2, month2, self.EARLY_MONTH_DAY)

            return {
                "Laycan Start Date": start_date.strftime('%Y-%m-%d'),
                "Laycan End Date": end_date.strftime('%Y-%m-%d')
            }
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse end month to early month format: {e}")
            return {"Laycan Start Date": None, "Laycan End Date": None}

    def _parse_day_range_month(self, day1: str, day2: str, month_str: str) -> Dict[str, Optional[str]]:
        """Parse format: '06-10 June'"""
        try:
            month = self._get_month_number(month_str)
            year = self._smart_year_detection(month)

            start_date = datetime(year, month, int(day1))
            end_date = datetime(year, month, int(day2))

            return {
                "Laycan Start Date": start_date.strftime('%Y-%m-%d'),
                "Laycan End Date": end_date.strftime('%Y-%m-%d')
            }
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse day range month format: {e}")
            return {"Laycan Start Date": None, "Laycan End Date": None}

    def _parse_second_half_month(self, month_str: str) -> Dict[str, Optional[str]]:
        """Parse format: '2H June'"""
        try:
            month = self._get_month_number(month_str)
            year = self._smart_year_detection(month)

            start_date = datetime(year, month, self.SECOND_HALF_START_DAY)
            end_date = self._get_end_of_month(year, month)

            return {
                "Laycan Start Date": start_date.strftime('%Y-%m-%d'),
                "Laycan End Date": end_date.strftime('%Y-%m-%d')
            }
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse second half month format: {e}")
            return {"Laycan Start Date": None, "Laycan End Date": None}

    def normalize_laycan(self, laycan_str: str) -> Dict[str, Optional[str]]:
        """Normalize laycan date formats with improved error handling"""
        if not laycan_str or not laycan_str.strip():
            return {"Laycan Start Date": None, "Laycan End Date": None}

        normalized = laycan_str.lower().replace("–", "-").strip()

        # Try each format pattern
        for date_format in DateFormat:
            match = re.search(date_format.value, normalized)
            if match:
                groups = match.groups()

                try:
                    if date_format == DateFormat.END_MONTH_TO_EARLY_MONTH:
                        return self._parse_end_month_to_early_month(groups[0], groups[1])
                    elif date_format == DateFormat.DAY_RANGE_MONTH:
                        return self._parse_day_range_month(groups[0], groups[1], groups[2])
                    elif date_format == DateFormat.SECOND_HALF_MONTH:
                        return self._parse_second_half_month(groups[0])

                except Exception as e:
                    logger.warning(f"Failed to parse {date_format.name}: {e}")
                    continue

        logger.warning(f"Unknown laycan format: {laycan_str}")
        return {"Laycan Start Date": None, "Laycan End Date": None}


class FreightCalculator:
    """Handles freight calculations with proper error handling"""

    @staticmethod
    def calculate_total_freight(freight_str: str, quantity_mt: Union[float, str]) -> Union[float, str]:
        """Calculate total freight based on freight string and quantity"""
        if freight_str == "N/A" or not isinstance(quantity_mt, (int, float)):
            return "N/A"

        try:
            # Per metric ton calculation
            if "pmt" in freight_str.lower():
                rate_match = re.search(r'[\d\.]+', freight_str)
                if rate_match:
                    rate = float(rate_match.group(0))
                    return rate * float(quantity_mt)

            # Lumpsum or million calculation
            elif "lumpsum" in freight_str.lower() or ' m' in freight_str.lower():
                value_match = re.search(r'[\d\.]+', freight_str)
                if value_match:
                    value = float(value_match.group(0))
                    if 'm' in freight_str.lower():
                        value *= 1_000_000
                    return value

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate freight: {e}")

        return "N/A"


class ShippingDataParser:
    """Main parser class with improved structure and error handling"""

    # Known entities (could be loaded from config file)
    KNOWN_CHARTERERS = [
        "P66", "Neste", "Bunge", "Cargill", "Nova", "Olam", "ENI",
        "SK Energy", "ICOF", "Kolmar", "Petroineos", "Wilmar", "GAM", "Aramco"
    ]

    KNOWN_CARGOS = [
        'UCO + Tallow', 'UCO/UCOME/Bio feedstock', 'UCO/Bio feedstocks', 'POME/Palms/UCO',
        'Palm/POME/EFBO/SBEO', 'SAF/UCO/FAME', 'Palm oil', 'Palmoil', 'Palm', 'POP',
        'BIOS', 'Fishoil', 'UCO', 'Benzene', 'MTBE'
    ]

    def __init__(self, default_year: Optional[int] = None):
        # Use current year by default, but allow override for testing or historical data
        self.laycan_parser = LaycanParser(default_year)
        self.freight_calculator = FreightCalculator()
        # Sort cargos by length (longest first) for better matching
        self.sorted_cargos = sorted(self.KNOWN_CARGOS, key=len, reverse=True)

    def _is_charterer_led_format(self, line: str) -> bool:
        """Check if line follows charterer-led format"""
        return any(line.strip().startswith(f"{charterer} /") for charterer in self.KNOWN_CHARTERERS)

    def _parse_charterer_led_format(self, line: str) -> ShippingRecord:
        """Parse charterer-led format: 'Charterer / Vessel / Quantity Cargo / Ports'"""
        record = ShippingRecord()

        try:
            parts = [p.strip() for p in line.split(' / ')]

            if len(parts) >= 2:
                record.charterer = parts[0]
                record.vessel_name = parts[1]

            if len(parts) >= 3:
                quantity_cargo_match = re.search(r"((?:\d{1,3},)?\d+)\s?MT\s+(.*)", parts[2], re.IGNORECASE)
                if quantity_cargo_match:
                    quantity_str = re.sub(r'[^\d.]', '', quantity_cargo_match.group(1))
                    record.quantity_mt = float(quantity_str)
                    record.cargo = quantity_cargo_match.group(2).strip()

            if len(parts) >= 4 and ' to ' in parts[3]:
                port_parts = parts[3].split(' to ')
                if len(port_parts) == 2:
                    record.load_port = port_parts[0].strip()
                    record.discharge_port = port_parts[1].strip()

            # Extract laycan and freight from the full line
            self._extract_laycan_and_freight(line, record)

        except Exception as e:
            logger.warning(f"Failed to parse charterer-led format: {e}")

        return record

    def _parse_standard_format(self, line: str) -> ShippingRecord:
        """Parse standard format with improved regex patterns"""
        record = ShippingRecord()
        work_line = str(line)

        try:
            # Extract laycan
            laycan_pattern = (
                r"(\d{1,2}-\d{1,2}\s+[A-Za-z]+|"
                r"\b[Ee]arly\s+[A-Za-z]+|"
                r"\b[Ee]ly\s+[A-Za-z]+|"
                r"\d{1,2}\s+[A-Za-z]+\s+[–-]\s+\d{1,2}\s+[A-Za-z]+|"
                r"\b[Ee]nd\s+[A-Za-z]+\s*–\s*\b[Ee]ly\s+[A-Za-z]+|"
                r"\b[Ee]nd\s+[A-Za-z]+|"
                r"\b2[Hh]\s+[A-Za-z]+)"
            )

            laycan_match = re.search(laycan_pattern, work_line, re.IGNORECASE)
            if laycan_match:
                record.laycan = laycan_match.group(1).strip()
                work_line = work_line.replace(laycan_match.group(1), '')

            # Extract freight
            freight_pattern = (
                r"(USD\s+[\d\.]+[M]?\s+Lumpsum|"
                r"Usd\s+[\d\.]+\s+pmt|"
                r"Usd\s+[\d\.]+\s*K\s+PD|"
                r"Usd\s+low\s+\d+ies|"
                r"Usd\s+hi\s+\d+ies|"
                r"Usd\s+[\d\.]+\s+M)"
            )

            freight_match = re.search(freight_pattern, work_line, re.IGNORECASE)
            if freight_match:
                record.freight = freight_match.group(1)
                work_line = work_line.replace(freight_match.group(1), '')

            # Extract charterer
            charterer_pattern = r"\b(" + "|".join(re.escape(c) for c in self.KNOWN_CHARTERERS) + r")\b"
            charterer_match = re.search(charterer_pattern, work_line, re.IGNORECASE)
            if charterer_match:
                record.charterer = charterer_match.group(1)
                work_line = work_line.replace(charterer_match.group(1), '')

            # Clean up RNR suffix
            work_line = re.sub(r'\s+RNR\s*$', '', work_line).strip()

            # Extract vessel name and quantity
            self._extract_vessel_and_quantity(work_line, record)

        except Exception as e:
            logger.warning(f"Failed to parse standard format: {e}")

        return record

    def _extract_vessel_and_quantity(self, work_line: str, record: ShippingRecord) -> None:
        """Extract vessel name, quantity, and cargo from work line"""
        quantity_pattern = r"((?:\d+-)?(?:\d{1,3},)?\d+\.?\d*k?)\s?(?:Mtons|ktons|ktrons|MT)"
        quantity_match = re.search(quantity_pattern, work_line, re.IGNORECASE)

        if quantity_match:
            record.vessel_name = work_line[:quantity_match.start()].strip()

            # Parse quantity
            val_str = quantity_match.group(1).split('-')[0]
            is_k = 'k' in quantity_match.group(0).lower()
            numeric_val = float(re.sub(r'[^\d.]', '', val_str))
            if is_k:
                numeric_val *= 1000
            record.quantity_mt = numeric_val

            # Extract cargo and ports
            remaining_str = work_line[quantity_match.end():].strip()
            self._extract_cargo_and_ports(remaining_str, record)

    def _extract_cargo_and_ports(self, remaining_str: str, record: ShippingRecord) -> None:
        """Extract cargo and ports from remaining string"""
        # Find matching cargo
        for cargo in self.sorted_cargos:
            if remaining_str.lower().startswith(cargo.lower()):
                record.cargo = cargo
                ports_str = remaining_str[len(cargo):].strip()

                # Clean up ratio suffix (e.g., "1/1")
                ports_str = re.sub(r'\s+\d/\d\s*$', '', ports_str).strip()

                # Extract ports
                if ' / ' in ports_str:
                    port_parts = [p.strip() for p in ports_str.split(' / ')]
                    if len(port_parts) >= 2:
                        record.load_port = port_parts[0]
                        record.discharge_port = port_parts[1]
                break

    def _extract_laycan_and_freight(self, line: str, record: ShippingRecord) -> None:
        """Extract laycan and freight from line"""
        # Laycan extraction
        laycan_match = re.search(r"(\d{1,2}-\d{1,2}\s+[A-Za-z]+)", line, re.IGNORECASE)
        if laycan_match:
            record.laycan = laycan_match.group(1)

        # Freight extraction
        freight_match = re.search(r"(USD\s+[\d\.]+[M]?\s+Lumpsum)", line, re.IGNORECASE)
        if freight_match:
            record.freight = freight_match.group(1)

    def _finalize_record(self, record: ShippingRecord) -> ShippingRecord:
        """Finalize record with laycan parsing and freight calculation"""
        # Parse laycan dates
        if record.laycan != "N/A":
            laycan_dates = self.laycan_parser.normalize_laycan(record.laycan)
            record.laycan_start_date = laycan_dates["Laycan Start Date"]
            record.laycan_end_date = laycan_dates["Laycan End Date"]

        # Calculate total freight
        record.total_freight_usd = self.freight_calculator.calculate_total_freight(
            record.freight, record.quantity_mt
        )

        return record

    def parse_shipping_data(self, text_data: str) -> List[Dict[str, Any]]:
        """Main parsing method with improved error handling"""
        if not text_data or not text_data.strip():
            logger.warning("Empty or invalid input data")
            return []

        records = []
        lines = text_data.strip().split('\n')

        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            try:
                if self._is_charterer_led_format(line):
                    record = self._parse_charterer_led_format(line)
                else:
                    record = self._parse_standard_format(line)

                record = self._finalize_record(record)
                records.append(record.to_dict())

            except Exception as e:
                logger.error(f"Failed to parse line {line_num}: {line[:50]}... Error: {e}")
                continue

        logger.info(f"Successfully parsed {len(records)} records from {len(lines)} lines")
        return records

    def save_to_excel(self, records: List[Dict[str, Any]], filename: str = "parsed_shipping_data.xlsx") -> bool:
        """Save records to Excel with error handling"""
        try:
            if not records:
                logger.warning("No records to save")
                return False

            df = pd.DataFrame(records)

            # Ensure output directory exists
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save to Excel
            df.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"Data successfully saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save to Excel: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Example usage
    parser = ShippingDataParser()  # Uses current year automatically

    sample_data = """
    P66 / Vessel A / 5000 MT UCO / Singapore to Rotterdam / 15-20 June / USD 500 Lumpsum
    Vessel B 3000 MT Palm oil Singapore / Rotterdam 2H July Neste USD 45 pmt
    """

    records = parser.parse_shipping_data(sample_data)
    success = parser.save_to_excel(records, "output/shipping_data.xlsx")

    if success:
        print("Parsing completed successfully!")
    else:
        print("Parsing failed!")