import unittest
from src.parser import parse_shipping_data


class TestShippingParser(unittest.TestCase):

    def test_parsing_examples(self):
        """
        Tests the parser with a variety of data formats from the brief.
        """
        test_cases = [
            {
                "input": "Seagull 09 10ktons Palm oil E.Malaysia / EC India  Usd 35 pmt  2H June Wilmar",
                "expected": {
                    'Vessel Name': 'Seagull 09',
                    'Cargo': 'Palm oil',
                    'Quantity (MT)': 10000.0,
                    'Load Port': 'E.Malaysia',
                    'Discharge Port': 'EC India',
                    'Laycan': '2H June',
                    'Freight': 'Usd 35 pmt',
                    'Total Freight (USD)': 350000.0,
                    'Charterer': 'Wilmar'
                }
            },
            {
                "input": "P66 / Seaways Moment / 32,000MT UCO + Tallow / Port Klang to USWC / 06-10 June / USD 2.15M Lumpsum",
                "expected": {
                    'Vessel Name': 'Seaways Moment',
                    'Cargo': 'UCO + Tallow',
                    'Quantity (MT)': 32000.0,
                    'Load Port': 'Port Klang',
                    'Discharge Port': 'USWC',
                    'Laycan': '06-10 June',
                    'Freight': 'USD 2.15M Lumpsum',
                    'Total Freight (USD)': 2150000.0,
                    'Charterer': 'P66'
                }
            },
            {
                "input": "NCC Danah   30-40ktons  UCO/Bio feedstocks    China + Straits / Spain – ARA Rge   RNR   end June – ely July   Kolmar",
                "expected": {
                    'Vessel Name': 'NCC Danah',
                    'Cargo': 'UCO/Bio feedstocks',
                    'Quantity (MT)': 30000.0,  # Note: Takes the first number in a range
                    'Load Port': 'China + Straits',
                    'Discharge Port': 'Spain – ARA Rge',
                    'Laycan': 'end June – ely July',
                    'Freight': 'N/A',  # RNR is not a standard freight format
                    'Total Freight (USD)': 'N/A',
                    'Charterer': 'Kolmar'
                }
            },
            {
                "input": "Dai Thanh   12ktons POP   Balikpapan / South China   Usd 29.00 pmt 25-30 Jun Nova",
                "expected": {
                    'Vessel Name': 'Dai Thanh',
                    'Cargo': 'POP',
                    'Quantity (MT)': 12000.0,
                    'Load Port': 'Balikpapan',
                    'Discharge Port': 'South China',
                    'Laycan': '25-30 Jun',
                    'Freight': 'Usd 29.00 pmt',
                    'Total Freight (USD)': 348000.0,
                    'Charterer': 'Nova'
                }
            },
            {
                "input": "Alfred N 23500 Mtons POME/Palms/UCO    China + Starits / Italy    Usd 2.85 M 1/1   2h June  ENI",
                "expected": {
                    'Vessel Name': 'Alfred N',
                    'Cargo': 'POME/Palms/UCO',
                    'Quantity (MT)': 23500.0,
                    'Load Port': 'China + Starits',
                    'Discharge Port': 'Italy',
                    'Laycan': '2h June',
                    'Freight': 'Usd 2.85 M',
                    'Total Freight (USD)': 2850000.0,
                    'Charterer': 'ENI'
                }
            }
        ]

        for i, case in enumerate(test_cases):
            with self.subTest(i=i):
                # Act
                parsed_result = parse_shipping_data(case["input"])

                # Assert
                # The parser returns a list, so we get the first (and only) item
                self.assertIsNotNone(parsed_result, "Parser returned None")
                self.assertEqual(len(parsed_result), 1, "Parser did not return exactly one record")
                self.assertEqual(parsed_result[0], case["expected"])


if __name__ == '__main__':
    unittest.main(verbosity=2)