# Texas Insurance Price Transparency (TiC) Data Pipeline

This repository contains tools and documentation for the automated discovery, extraction, and management of **Transparency in Coverage (TiC)** data for the state of Texas.

The project utilizes a **"Sieve-Based" Extraction Strategy** to convert multi-terabyte machine-readable files (MRFs) into manageable flat-file datasets suitable for policy analysis in Stata.

## 🚀 Project Overview

Insurance carriers (BCBS, UHC, etc.) are required by the CMS Transparency in Coverage Final Rule to publish monthly "Machine Readable Files" containing negotiated rates for every procedure and provider. Due to the massive scale of these files (often 100GB+ per JSON), standard download-and-process workflows are non-viable.

This pipeline solves the "Big Data" problem by:
1. **Automated Discovery:** Identifying specific employer/plan URLs using EINs or Table of Contents (TOC) indices.
2. **Streaming Extraction:** Parsing JSON data in real-time from the cloud without high memory overhead or local storage of the full 100GB files.
3. **Targeted Filtering:** Pulling data only for a specific "Menu" of CPT/HCPCS codes.

## 💡 Value & Research Impact

This project provides the "missing link" in healthcare price transparency. While previous work, such as the [Texas 2036 Hospital Pricing Tool](https://texas2036.shinyapps.io/hospital-pricing/), has successfully mapped hospital-side charge data, this pipeline enables a **360-degree view** of the healthcare market by extracting the insurer-side negotiated rates.

### Key Research Insights:
*   **Insurer vs. Hospital Alignment:** Comparing the rates hospitals claim to negotiate with the rates insurers actually report.
*   **Geographic Price Variation:** Identifying regional "price cliffs" across Texas for identical procedures.
*   **Market Power Analysis:** Evaluating how different insurance products (HMO vs. PPO) and health systems leverage their scale to influence pricing.
*   **Policy Evaluation:** Providing a baseline of real-world negotiated rates to inform legislative efforts regarding healthcare affordability and network adequacy.

By utilizing a "Sieve-Based" strategy, this repository makes it possible for researchers to conduct high-fidelity analysis of "Big Data" sources that were previously inaccessible due to technical and infrastructure constraints.

## 📁 Repository Structure

The repository has been expanded with modular scripts for a full end-to-end workflow:

| File | Description |
| :--- | :--- |
| **Workflow Scripts** | |
| `00_build_tx_npi.py` | Filters the national NPPES registry for Texas-specific NPIs to reduce join overhead. |
| `00a_fetch_nppes.py` | Automates the retrieval of the latest monthly NPPES data release. |
| `01_discover.py` | Modular URL discovery script (built to handle multiple providers). |
| `02_extract.py` | Production-grade "Sieve" script for high-volume streaming extraction. |
| `03_to_dta.py` | Converts extracted CSV data into Stata `.dta` format with standard labels. |
| `04_run.py` | Master orchestrator to run the full pipeline in sequence. |
| **Legacy/Support** | |
| `bcbs_url_discovery.py`| Specific tool for scraping BCBS TX ASO links by EIN. |
| `tic_extractor.py` | Lightweight version of the extraction logic for testing. |
| `tic_common.py` | Shared utility functions (compression handling, schema paths). |
| `build_dta.do` | Stata do-file for final data cleaning and harmonization. |
| **Data & Docs** | |
| `data_elements.xlsx` | The master schema defining variables (columns) for the committee. |
| `data_elements_menu.csv`| The categorical procedure list (CPT/HCPCS) used for filtering. |
| `initialtest_extracted_rates.csv` | Large-scale test output (50MB+) from the prototype run. |
| `nextsteps_plan.md` | Strategic plan and committee discussion points. |
| `originalask.md` | Technical background and project requirements. |

## 🛠 Setup & Requirements

The tools are written in Python 3 and optimized for macOS. To install the necessary libraries:

```bash
python3 -m pip install ijson requests beautifulsoup4 pandas openpyxl --break-system-packages
```

## 📖 Usage Instructions

1. **Setup NPI Filter:** Run `00_build_tx_npi.py` to prepare the Texas provider crosswalk.
2. **Discover URLs:** Update the EIN list in `01_discover.py` and run it to generate `discovered_mrf_urls.csv`.
3. **Run Extraction:** Execute `02_extract.py` to stream and filter the JSON files.
4. **Finalize:** Use `03_to_dta.py` or `build_dta.do` to create your analysis-ready Stata dataset.

## 🌐 Expanding to Other Providers

While current development focuses on **BCBS TX**, the pipeline is architected for full extensibility:

*   **Schema Consistency:** All providers (UHC, Cigna, Aetna, etc.) are required to use the same CMS JSON schema. The "Sieve" logic in `02_extract.py` will work across carriers without modification.
*   **TOC Mapping:** Expansion requires identifying the central Table of Contents (TOC) URL for each carrier. 
    *   *UHC:* `https://transparency-in-coverage.uhc.com/`
    *   *Anthem/Elevance:* `https://www.anthem.com/machine-readable-file/search/`
*   **Discovery Layer:** To add a new provider, create a new discovery class in `tic_common.py` to handle that specific carrier's URL index format.

## 📊 Data Integrity
The extracted data includes audit-trail elements (`source_file_url`, `source_file_hash`) to ensure research reproducibility. All rates are stored in USD with modifiers preserved to prevent "apples-to-oranges" comparisons.

## ✍️ Author
**Eric A. Booth**  
Senior Policy Researcher / Data Lead  
**Texas 2036**  
[eric.a.booth@gmail.com](mailto:eric.a.booth@gmail.com) | [www.texas2036.org](https://www.texas2036.org)

## ⚖️ License
Licensed under the MIT License. See `LICENSE` for details.
