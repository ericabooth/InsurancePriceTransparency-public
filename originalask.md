# Original Project Request: Insurance Price Transparency

**Core Objective:** Investigate the viability of extracting insurance transparency data (Transparency in Coverage) into a manageable flat-file dataset for Texas policy analysis, parallel to existing hospital transparency work.

---

### Context & Background (Charles Miller)
The request follows up on efforts to replicate or extend the methodology found in [Texas 2036's Health Price Transparency work](https://texas2036.org/health-price-transparency/health-price-transparency-methodology/).

#### **Key Data Sources Identified:**
*   **BCBS TX:** [Machine Readable Files Landing Page](https://www.bcbstx.com/member/machine-readable-files)
*   **UnitedHealthcare:** [Transparency in Coverage Portal](https://transparency-in-coverage.uhc.com/)
*   **Anthem/Elevance:** [MRF Search Tool](https://www.anthem.com/machine-readable-file/search/)

#### **Methodology Insights:**
*   **Insurers vs. Employers:** For ASO (Administrative Services Only) groups, insurers host files on behalf of employers, often indexed by the employer's **EIN**.
*   **Targeted Search (BCBS):** A specific URL pattern exists for finding employer-specific files if the EIN is known: `https://www.bcbstx.com/asomrf?EIN={EIN}`
*   **External References:** [DoltHub's "State of Hospital Price Transparency"](https://www.dolthub.com/blog/2025-01-28-state-of-hospital-price-transparency-data/) provides a benchmark for how others are tackling this technical hurdle.
*   **Existing Tools:** This work is intended to complement the [Hospital Pricing Tool](https://texas2036.shinyapps.io/hospital-pricing/) developed by JA for Texas 2036.

#### **Feasibility Note:**
The goal is to determine the structure and feasibility of extracting these massive files into a Stata-centric workflow without needing to download the entire terabyte-scale universe of data.
