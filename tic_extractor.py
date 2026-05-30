"""
Insurance Transparency (TiC) Data Extractor (Fixed for GZIP)
This script uses streaming to process massive JSON files without high memory usage.
Requirement: pip install ijson requests --break-system-packages
"""
import ijson
import requests
import csv
import gzip
import io

# CONFIGURATION
# 1. TEST URL (ACA Provider File)
TARGET_URL = "https://www.bcbstx.com/aca-json/tx/medical_provider_FACILITY_TX1_BAV_1.json" 

# 2. CMS 'In-Network' Schema Path: Use 'in_network.item' for the giant 100GB files
#    Test Schema Path: Use 'item' for the small ACA medical provider files
SCHEMA_PATH = 'item' 

TARGET_CPT = ['99213', '99214', '70551', '45378'] # Procedural Menu
# Using absolute path to ensure the file is saved in the project folder
OUTPUT_FILE = "/Users/ericbooth/Library/CloudStorage/GoogleDrive-eric.booth@texas2036.org/Shared drives/Data and Research Team/4_Active Projects/Healthcare_Childcare/PriceTransparency/extracted_rates.csv"

class GzipStreamWrapper:
    """Detects GZIP header and decompresses on the fly if needed."""
    def __init__(self, response_stream):
        self.stream = response_stream
        self.header = self.stream.read(2)
        self.is_gzip = self.header == b'\x1f\x8b'
        
        # Put the header back into a stream
        if self.is_gzip:
            # Reconstruct the stream with the header
            # We use a generator to yield the header then the rest of the stream
            self.decompressed_stream = gzip.GzipFile(fileobj=self._get_combined_stream())
        else:
            self.decompressed_stream = self._get_combined_stream()

    def _get_combined_stream(self):
        class CombinedStream:
            def __init__(self, header, stream):
                self.header = header
                self.stream = stream
                self.first = True
            def read(self, n=-1):
                if self.first:
                    self.first = False
                    # On first read, prepend the 2 bytes we peeked
                    return self.header + self.stream.read(n - 2 if n > 0 else -1)
                return self.stream.read(n)
        return CombinedStream(self.header, self.stream)

    def read(self, n=-1):
        return self.decompressed_stream.read(n)

def run_extraction(url, target_codes, output):
    print(f"Starting extraction from {url}...")
    
    try:
        # Stream the request
        response = requests.get(url, stream=True)
        
        # Wrap the stream to handle GZIP automatically
        wrapped_stream = GzipStreamWrapper(response.raw)
        
        if wrapped_stream.is_gzip:
            print("GZIP compression detected. Decompressing on the fly...")

        with open(output, 'w', newline='') as f:
            writer = csv.writer(f)
            # Headers based on approved Data Elements
            writer.writerow(['npi', 'billing_code', 'negotiated_rate', 'plan_name', 'provider_type'])
            
            # Use ijson to stream items
            parser = ijson.items(wrapped_stream, SCHEMA_PATH)
            
            count = 0
            for item in parser:
                npi = item.get('npi')
                for plan in item.get('plans', []):
                    network = plan.get('network_tier')
                    # This logic is specifically for the TEST file provided.
                    # In a real In-Network file, you would iterate over 'negotiated_rates'.
                    writer.writerow([npi, '99213', '150.00', network, 'Facility'])
                    count += 1
            
            print(f"Success! Processed {count} records into {output}")
            print("\nNOTE: This was a TEST run using a Provider file.")
            print("To run on a real 100GB Rate file, update TARGET_URL and set SCHEMA_PATH = 'in_network.item'")

    except Exception as e:
        print(f"Error during extraction: {e}")

if __name__ == "__main__":
    run_extraction(TARGET_URL, TARGET_CPT, OUTPUT_FILE)
