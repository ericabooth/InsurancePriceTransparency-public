"""
BCBS TX MRF URL Discovery Tool
Automates the retrieval of 'In-Network Negotiated Rate' URLs for a list of EINs.
Requirement: pip install requests beautifulsoup4 --break-system-packages
"""
import requests
from bs4 import BeautifulSoup
import csv
import time

# List of EINs to query (9 digits, no dash)
# You can replace this with a load from your DOL 5500 Master List later
EIN_LIST = ['272508985', '741109635', '750800701'] 

OUTPUT_CSV = "/Users/ericbooth/Library/CloudStorage/GoogleDrive-eric.booth@texas2036.org/Shared drives/Data and Research Team/4_Active Projects/Healthcare_Childcare/PriceTransparency/discovered_mrf_urls.csv"

def discover_urls(eins):
    results = []
    
    # BCBS TX ASO MRF Tool Endpoint
    BASE_URL = "https://www.bcbstx.com/asomrf"
    
    print(f"Starting URL discovery for {len(eins)} EINs...")
    
    for ein in eins:
        print(f"Querying EIN: {ein}...")
        try:
            # Step 1: Query the ASO tool
            # Note: Insurers often use dynamic JavaScript, but we'll try a direct POST/GET first.
            # If this fails, we move to a 'Selenium' approach for headless browsing.
            params = {'EIN': ein}
            response = requests.get(BASE_URL, params=params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Step 2: Search for 'In-Network' links
                # Links typically contain 'in-network-rates' and end in .json.gz
                found = False
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'in-network-rates' in href.lower() and href.endswith('.json.gz'):
                        results.append({'ein': ein, 'mrf_url': href, 'status': 'Success'})
                        print(f"  [+] Found: {href[:60]}...")
                        found = True
                        break
                
                if not found:
                    results.append({'ein': ein, 'mrf_url': '', 'status': 'No In-Network File Found'})
                    print(f"  [-] No specific In-Network file found for this EIN.")
            else:
                results.append({'ein': ein, 'mrf_url': '', 'status': f'Error: {response.status_code}'})
        
        except Exception as e:
            results.append({'ein': ein, 'mrf_url': '', 'status': f'Exception: {str(e)}'})
            print(f"  [!] Error querying {ein}: {e}")
            
        # Polite delay to avoid anti-bot triggering
        time.sleep(1)

    # Save to CSV
    keys = results[0].keys()
    with open(OUTPUT_CSV, 'w', newline='') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
        
    print(f"\nDiscovery complete! Mapping saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    discover_urls(EIN_LIST)
