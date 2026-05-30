# Texas Insurance Price Transparency (TiC) Data Pipeline

This repository contains tools and documentation for the automated discovery, extraction, and management of **Transparency in Coverage (TiC)** data for the state of Texas.

The project utilizes a **"Sieve-Based" Extraction Strategy** to convert multi-terabyte machine-readable files (MRFs) into manageable flat-file datasets suitable for policy analysis in Stata.

## 🚀 Project Overview

Insurance carriers (BCBS, UHC, etc.) are required by the CMS Transparency in Coverage Final Rule to publish monthly "Machine Readable Files" containing negotiated rates for every procedure and provider. Due to the massive scale of these files (often 100GB+ per JSON), standard download-and-process workflows are non-viable.

This pipeline solves the "Big Data" problem by:
1. **Automated Discovery:** Identifying specific employer/plan URLs using EINs.
2. **Streaming Extraction:** Parsing JSON data in real-time from the cloud without high memory overhead or local storage of the full 100GB files.
3. **Targeted Filtering:** Pulling data only for a specific "Menu" of CPT/HCPCS codes.

## 📁 Repository Structure

| File | Description |
| :--- | :--- |
| `data_elements.xlsx` | The master schema defining the variables (columns) in our final dataset. |
| `bcbs_url_discovery.py` | **The Scout:** Automates the retrieval of download URLs for a list of EINs via the BCBS TX ASO tool. |
| `tic_extractor.py` | **The Sieve:** Streams JSON files, decompresses GZIP on the fly, and filters for target CPT codes. |
| `nextsteps_plan.md` | Strategic plan and questions for the review committee. |
| `originalask.md` | Background on the project and original technical requirements. |
| `sample_extracted_data.csv` | A proof-of-concept dataset showing the expected output format. |

## 🛠 Setup & Requirements

The tools are written in Python 3. To install the necessary libraries on macOS:

```bash
python3 -m pip install ijson requests beautifulsoup4 pandas --break-system-packages
```

## 📖 Usage Instructions

### Phase 1: URL Discovery
Update the `EIN_LIST` in `bcbs_url_discovery.py` with your target Texas employer EINs (sourced from DOL Form 5500), then run:

```bash
python3 bcbs_url_discovery.py
```
*Output: `discovered_mrf_urls.csv` containing a mapping of EINs to direct download links.*

### Phase 2: Data Extraction
Update the `TARGET_URL` in `tic_extractor.py` with a URL from the discovery phase and set the `SCHEMA_PATH` to `'in_network.item'`. Then run:

```bash
python3 tic_extractor.py
```
*Output: `extracted_rates.csv` containing the negotiated rates for your target CPT codes.*

## 📊 Data Elements
The extracted data includes essential variables for policy research, including:
* **Negotiated Rates** & **Arrangement Types** (FFS vs. Bundle)
* **Provider NPIs** & **TINs**
* **Billing Modifiers**
* **Geographic Indicators** (Zip/Address)

## ⚖️ License & Integrity
Data is sourced from public machine-readable files provided by insurance carriers in compliance with the CMS Transparency in Coverage Rule. 
*Note: This pipeline includes audit-trail elements (source hashes and URLs) to ensure research reproducibility.*
