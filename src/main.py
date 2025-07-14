import os
import sys
from src.parser import parse_shipping_data, save_to_excel
from src.utils import normalize_laycan, KNOWN_CHARTERERS


def get_pasted_data():
    """
    Captures multi-line text pasted into the terminal by the user.

    The user signals the end of their input by pressing Ctrl+D (on Mac/Linux)
    or Ctrl+Z followed by Enter (on Windows).
    """
    print("📋 Please paste your unstructured shipping data below.")
    print("   Press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows) to finish.")
    print("-" * 60)

    # sys.stdin.read() captures all input until the EOF (End-of-File) signal
    return sys.stdin.read()


def main():
    """
    The main function to run the data parsing application.
    """
    print("--- 🚢 Shipping Data Parsing Tool ---")

    # 1. Get the raw data from the user
    raw_data = get_pasted_data()

    if not raw_data.strip():
        print("\n❌ No data was provided. Exiting application.")
        return

    # 2. Parse the data using the imported function
    print("\n⚙️  Parsing the provided data...")
    parsed_records = parse_shipping_data(raw_data)

    if not parsed_records:
        print("⚠️  Could not parse any valid records from the provided text.")
        return

    print(f"✅ Successfully parsed {len(parsed_records)} records.")

    # 3. Save the clean data to an Excel file
    output_filename = "parsed_shipping_data.xlsx"
    print(f"💾 Saving the clean data to '{output_filename}'...")
    save_to_excel(parsed_records, output_filename)

    # 4. Provide confirmation to the user
    output_path = os.path.abspath(output_filename)
    print("\n🎉 Process complete!")
    print(f"   Your file is ready at: {output_path}")


if __name__ == "__main__":
    main()