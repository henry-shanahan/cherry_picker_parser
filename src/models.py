#!/usr/bin/env python3
"""
Data models and classes for shipping data parsing.
"""

from dataclasses import dataclass
from typing import Dict, Union, Optional


@dataclass
class ShippingRecord:
    """Data class representing a parsed shipping record."""

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
        """Convert shipping record to dictionary format for DataFrame."""
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

    def is_complete(self) -> bool:
        """Check if record has essential information."""
        return (
                self.vessel_name != "N/A" and
                self.quantity_mt != "N/A" and
                isinstance(self.quantity_mt, (int, float))
        )

    def has_laycan_dates(self) -> bool:
        """Check if record has laycan date information."""
        return self.laycan_start_date is not None

    def __str__(self) -> str:
        """String representation of shipping record."""
        return f"ShippingRecord(vessel='{self.vessel_name}', cargo='{self.cargo}', quantity={self.quantity_mt})"

    def __repr__(self) -> str:
        """Developer representation of shipping record."""
        return self.__str__()