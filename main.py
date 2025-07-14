import os
import sys
from pathlib import Path
from src.parser import ShippingDataParser


def get_pasted_data():
    """
    Captures multi-line text pasted into the terminal by the user.

    The user signals the end of their input by pressing Ctrl+D (on Mac/Linux)
    or Ctrl+Z followed by Enter (on Windows).
    """
    print("📋 Please paste your unstructured shipping data below.")
    print("   Press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows) to finish.")
    print("-" * 60)

    try:
        # sys.stdin.read() captures all input until the EOF (End-of-File) signal
        return sys.stdin.read()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error reading input: {e}")
        sys.exit(1)


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

    # 2. Initialize the parser
    print("\n⚙️  Initializing parser...")
    parser = ShippingDataParser()

    # 3. Parse the data using the improved parser
    print("⚙️  Parsing the provided data...")
    try:
        parsed_records = parser.parse_shipping_data(raw_data)
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        return

    if not parsed_records:
        print("⚠️  Could not parse any valid records from the provided text.")
        print("   Check the logs above for more details on what went wrong.")
        return

    print(f"✅ Successfully parsed {len(parsed_records)} records.")

    # 4. Save the clean data to an Excel file
    output_filename = "parsed_shipping_data.xlsx"
    print(f"💾 Saving the clean data to '{output_filename}'...")

    try:
        success = parser.save_to_excel(parsed_records, output_filename)
        if not success:
            print("❌ Failed to save the Excel file. Check the logs above for details.")
            return
    except Exception as e:
        print(f"❌ Error saving to Excel: {e}")
        return

    # 5. Provide confirmation to the user
    output_path = Path(output_filename).resolve()
    print("\n🎉 Process complete!")
    print(f"   Your file is ready at: {output_path}")

    # 6. Optional: Show a summary of what was parsed
    print(f"\n📊 Summary:")
    print(f"   - Total records: {len(parsed_records)}")

    # Count records with complete data
    complete_records = sum(1 for record in parsed_records
                           if record.get('Vessel Name', 'N/A') != 'N/A'
                           and record.get('Quantity (MT)', 'N/A') != 'N/A')
    print(f"   - Complete records: {complete_records}")

    # Count records with laycan dates
    laycan_records = sum(1 for record in parsed_records
                         if record.get('Laycan Start Date') is not None)
    print(f"   - Records with laycan dates: {laycan_records}")


if __name__ == "__main__":
    main()