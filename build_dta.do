*! build_dta.do — Stata-native alternative to 03_to_dta.py
*! Imports the stage-2 long CSVs and saves labeled .dta files, then merges.
*! Cross-platform (Mac/Windows). Run from the project root or set `root`.

clear all
set more off
local root "`c(pwd)'"          // adjust if not launching from project root
local stg  "`root'/data/staging"
local out  "`root'/data/dta"
cap mkdir "`out'"

* ---- rates (long: one row per code x provider_group x price) -------------
import delimited "`stg'/rates_long.csv", varnames(1) case(preserve) clear ///
    stringcols(_all) encoding("utf-8")
destring negotiated_rate, replace force

label var billing_code        "Procedure/service code"
label var billing_code_type   "Code system (CPT/HCPCS/MS-DRG/...)"
label var negotiated_rate     "Negotiated amount ($; pct if type=percentage)"
label var negotiated_type     "Rate basis"
label var billing_class       "professional/institutional/both"
label var setting             "inpatient/outpatient/both"
label var provider_group_id   "FK -> providers crosswalk"
compress
save "`out'/rates_long.dta", replace

* ---- provider crosswalk (one row per provider_group_id x npi) ------------
import delimited "`stg'/providers.csv", varnames(1) case(preserve) clear ///
    stringcols(_all) encoding("utf-8")
compress
save "`out'/providers.dta", replace

* ---- example merge: attach NPIs to rates ---------------------------------
* use "`out'/rates_long.dta", clear
* joinby provider_group_id using "`out'/providers.dta"   // many-to-many on gid
* note: rates x providers is intentionally a 1-to-many fan-out; keep separate
*       unless you need provider-level rows, to control .dta size.

di as result "Done: rates_long.dta + providers.dta in `out'"
