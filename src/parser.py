import re
import pandas as pd
from utils import normalize_laycan, KNOWN_CHARTERERS


def parse_shipping_data(text_data: str):
    """
    Parses unstructured shipping data to extract key information, including
    normalized dates for analysis.

    Args:
        text_data: A string containing one or more lines of shipping data.

    Returns:
        A list of dictionaries, where each dictionary represents a parsed record.
    """
    records = []

    # Regex patterns to find specific pieces of information in a line of text.
    vessel_name_regex = r"^[A-Za-z0-9\s]+?(?=\s+\(?-?\d+|\s+\d{2,}\s?Mtons)"
    # Updated to be more flexible and handle more cargo name variations.
    cargo_quantity_regex = r"(\d{2,}(?:,\d{3})*|\d+\.?\d*k?)\s?(?:Mtons|ktons|ktrons|MT)\s+([A-Za-z0-9\s\/+]+?)\s+(?=[A-Za-z0-9\s]+\s*\/)"
    laycan_regex = r"(\d{1,2}-\d{1,2}\s+[A-Za-z]+|\b[Ee]arly\s+[A-Za-z]+|\b[Ee]ly\s+[A-Za-z]+|\d{1,2}\s+[A-Za-z]+\s+–\s+\d{1,2}\s+[A-Za-z]+|\b[Ee]nd\s+[A-Za-z]+\s*–\s*\b[Ee]ly\s+[A-Za-z]+|\b[Ee]nd\s+[A-Za-z]+|\b2H\s+[A-Za-z]+)"
    freight_regex = r"(USD\s+[\d\.]+[M]?\s+Lumpsum|Usd\s+[\d\.]+\s+pmt|Usd\s+[\d\.]+\s*K\s+PD|Usd\s+low\s+\d+ies|Usd\s+hi\s+\d+ies|Usd\s+[\d\.]+\s+M)"
    ports_regex = r"([A-Za-z0-9\s\.\+]+?)\s+\/\s+([A-Za-z0-9\s\.\-]+?)(?=\s+Usd|\s+RNR|\s+\d{1,2}-\d{1,2}\s+[A-Za-z]+|\s+\b[Ee]ly\b|\s+\b2H\b)"
    charterer_regex = r"\b(" + "|".join(KNOWN_CHARTERERS) + r")\b"

    for line in text_data.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # This dictionary structure now includes fields for normalized dates.
        record = {
            "Vessel Name": "N/A",
            "Cargo": "N/A",
            "Quantity (MT)": "N/A",
            "Load Port": "N/A",
            "Discharge Port": "N/A",
            "Laycan": "N/A",
            "Laycan Start Date": "N/A",
            "Laycan End Date": "N/A",
            "Freight": "N/A",
            "Total Freight (USD)": "N/A",
            "Charterer": "N/A"
        }

        # Extract information using the regex patterns
        vessel_match = re.search(vessel_name_regex, line)
        if vessel_match:
            record["Vessel Name"] = vessel_match.group(0).strip()

        cargo_quantity_match = re.search(cargo_quantity_regex, line, re.IGNORECASE)
        if cargo_quantity_match:
            quantity_str = cargo_quantity_match.group(1).lower().replace('k', '000')
            record["Quantity (MT)"] = float(re.sub(r'[^\d.]', '', quantity_str))
            record["Cargo"] = cargo_quantity_match.group(2).strip()

        ports_match = re.search(ports_regex, line)
        if ports_match:
            record["Load Port"] = ports_match.group(1).strip()
            record["Discharge Port"] = ports_match.group(2).strip()

        laycan_match = re.search(laycan_regex, line)
        if laycan_match:
            raw_laycan = laycan_match.group(0).strip()
            record["Laycan"] = raw_laycan

            # *** Use the imported normalize_laycan function ***
            normalized_dates = normalize_laycan(raw_laycan)
            record["Laycan Start Date"] = normalized_dates.get("start_date")
            record["Laycan End Date"] = normalized_dates.get("end_date")

        freight_match = re.search(freight_regex, line, re.IGNORECASE)
        if freight_match:
            freight_str = freight_match.group(0)
            record["Freight"] = freight_str.strip()
            if "pmt" in freight_str.lower() and isinstance(record["Quantity (MT)"], float):
                rate = float(re.search(r'[\d\.]+', freight_str).group(0))
                record["Total Freight (USD)"] = rate * record["Quantity (MT)"]
            elif "lumpsum" in freight_str.lower() or ' M' in freight_str:
                value_str = re.search(r'[\d\.]+', freight_str).group(0)
                value = float(value_str)
                if 'm' in freight_str.lower():
                    value *= 1_000_000
                record["Total Freight (USD)"] = value

        charterer_match = re.search(charterer_regex, line, re.IGNORECASE)
        if charterer_match:
            record["Charterer"] = charterer_match.group(0)

        records.append(record)

    return records


def save_to_excel(records, filename="parsed_shipping_data.xlsx"):
    """
    Saves the parsed data to an Excel file.

    Args:
        records: A list of dictionaries with the parsed data.
        filename: The name of the Excel file to save.
    """
    df = pd.DataFrame(records)
    df.to_excel(filename, index=False)
    print(f"Data successfully saved to {filename}")


# This block runs when you execute the script directly
if __name__ == '__main__':
    pasted_data = """
    P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum
    P66 / Seaways Mystery / 30,000MT BIOS / Tianjin to UKC / Early June / USD 2.5M Lumpsum bss 1/1
    Ginga Maya  18500 Mtons Fishoil and UCO  Can Tho and 2P Korea / USG   RNR   10-20 Jun  DGD
    Hafnia Tanzanite   42.3ktons Palm/POME/EFBO/SBEO  3Straits / Rotterdam   Usd 2.8 3/1   21-25 June  Neste
    Augenstern  (49Ktons  blt ’24) n  Trip T/C  delivery Sth korea  / Re-del Medcont   Usd 25,000   25 Jun – 5 July   Bunge
    Stena Impression  (49tkons ‘blt ’15)   Trip t/C  Del Haldia  / Re-del MedcontUSA  Usd 24K PD   1-10 Jun  Cargill - Failed
    Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova
    Sea Gull 18   12ktons POP Kumai / China    Usd 30 pmt bss sth  Ely Jun  Olam
    Alfred N 23500 Mtons POME/Palms/UCO    China + Starits / Italy    Usd 2.85 M 1/1   2h June  ENI
    Solar Susie  30ktons UCO/UCOME/Bio feedstock   China / ARAG   USd hi 2 M  1/1   10-20 Jun   SK Energy
    M Bristol   26ktons Palms   3 Straits  / 3 Med-cont rge   Usd 106 pmt 3/3   ely Jun  ICOF
    NCC Danah   30-40ktons  UCO/Bio feedstocks    China + Straits / Spain – ARA Rge   RNR   end June – ely July   Kolmar
    Boxer  35ktons SAF/UCO/FAME      China  / ARA     RNR    1-10 Jul      Petroineos  - on subs
    Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar
    Chemtec  12ktrons  Palmoil   Tarjun / China   Usd hi 20ies   2H June    GAM
    Golden Sun  38/40ktons MTBE  North China / ARA  Usd 2.6 M 1/1   end June / Ely July    Kolmar
    Bao Feng Hua 1 8600  Benzene  Kandla / Jubail   Usd low 30ies    17-25 June Aramco
    """

    parsed_records = parse_shipping_data(pasted_data)

    # Display the results in the console using pandas for a cleaner table format
    print("--- Parsed Data ---")
    df = pd.DataFrame(parsed_records)
    print(df.to_string())

    # Save the results to an Excel file
    save_to_excel(parsed_records)