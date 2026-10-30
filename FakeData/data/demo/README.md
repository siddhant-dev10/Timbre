# Timbre Master Synthetic Civic Dataset & Verification Workbook

This directory houses the consolidated, authoritative synthetic demo dataset for **Timbre**, an AI-powered Indian government-services assistant.

The dataset is consolidated into a single human-readable Excel workbook with 8 structured worksheets, accompanied by companion CSV exports for backend database ingestion.

---

## Deliverables & File Structure

| File | Type | Purpose | Dimensions |
| :--- | :--- | :--- | :--- |
| **[`Timbre_Master_Dataset.xlsx`](Timbre_Master_Dataset.xlsx)** | **Master Excel Workbook** | Single authoritative workbook containing all consolidated data, scheme catalogue, simulation scenarios, demo workflows, data dictionary, QA validation report, and source inventory. | **8 Worksheets**, 100 Citizens, 18 Services, 100 Scenarios |
| **[`Timbre_Master_Citizens.csv`](Timbre_Master_Citizens.csv)** | Backend CSV Export | UTF-8 CSV containing all 32 columns of synthetic citizen demographic records for database seeding (`COPY citizens ...`). | 100 Rows, 32 Columns |
| **[`Timbre_Master_Services.csv`](Timbre_Master_Services.csv)** | Backend CSV Export | UTF-8 CSV containing the 18 verified Indian statutory schemes and portal links. | 18 Rows, 10 Columns |
| **[`Timbre_Master_Scenarios.csv`](Timbre_Master_Scenarios.csv)** | Backend CSV Export | UTF-8 CSV containing the 100 1-to-1 eligibility evaluation scenarios with statutory rationales and next steps. | 100 Rows, 9 Columns |
| `Timbre_Fake_Citizens.xlsx` | Legacy Excel Export | Pre-existing 4-sheet legacy demo workbook (preserved for backward compatibility). | 4 Worksheets |
| `Timbre_Fake_Citizens.csv` | Legacy CSV Export | Pre-existing 32-column citizen CSV export (preserved for backward compatibility). | 100 Rows, 32 Columns |

---

## Workbook Architecture (8 Worksheets)

The master workbook [`Timbre_Master_Dataset.xlsx`](Timbre_Master_Dataset.xlsx) is organized into 8 color-coded worksheets:

### Sheet 1: `Dashboard` (Navy `#1E3A8A`)
- **Executive Summary & KPIs**: Total synthetic citizens (100), statutory schemes (18), simulation scenarios (100), duplicate citizen IDs (0), missing required fields (0), `demo_only=TRUE` records (100), services awaiting verification (0).
- **Dynamic Excel Formulas**: Live formulas (`=COUNTA(...)`, `=COUNTIF(...)`) alongside pre-calculated integer values for headless and native spreadsheet compatibility.
- **Safety Callout**: Prominent warning highlighting synthetic nature, non-dialable phone placeholders (`DEMO-PHONE-xxxx`), and `@example.com` domains.
- **Worksheet Directory**: Index detailing name, category, row count, column count, primary key, and description for every sheet.
- **Legal & Compliance Assurances**: Formal notices on DPDP Act 2023 Section 2(t) compliance, TRAI telephony safeguards, zero-credential guarantee, and deterministic reproducibility.

### Sheet 2: `Citizens` (Blue `#2563EB`)
- **100 Synthetic Profiles**: Fictional Indian citizens across 22 States and Union Territories.
- **32 Columns**: Complete demographic coverage:
  - `citizen_id` (`CIT-0001` to `CIT-0100`), `full_name`, `age` (16–85), `date_of_birth` (ISO `YYYY-MM-DD`), `gender`, `state`, `district`, `city_or_village`, `rural_or_urban`, `preferred_language` (27 languages/dialects), `education_level`, `occupation` (71 trades), `employment_status`, `annual_family_income_inr` (formatted currency `₹#,##,##0`), `family_size`, `marital_status`, `has_children`, `number_of_children`, `disability_status`, `student_status`, `farmer_status`, `senior_citizen_status` (`age >= 60`), `demo_phone`, `demo_email`, `life_event`, `life_event_date`, `potential_government_services`, `eligibility_notes`, `required_documents`, `application_channel`, `verification_status`, and `demo_only` (`TRUE`).
- **Excel Table & Filters**: Formatted as `CitizensMasterTable` with frozen header row (`A2`), data validation dropdowns, and alternating row striping.

### Sheet 3: `Government Services` (Teal `#0D9488`)
- **18 Verified Schemes**: Statutory Indian government schemes across healthcare, agriculture, social pensions, civil identity, education, and livelihood.
- **10 Columns**: `service_id`, `service_name`, `service_category`, `intended_beneficiaries`, `basic_eligibility`, `commonly_required_documents`, `official_application_portal`, `official_source_url`, `last_verified_date`, `verification_notes`.
- **Verified Portals**: Clickable hyperlinks pointing strictly to official `.gov.in` and `.nic.in` domains (e.g. Election Commission `voters.eci.gov.in`, Parivahan `parivahan.gov.in`, PM-KISAN `pmkisan.gov.in`, PM-JAY `beneficiary.nha.gov.in`).
- **Excel Table**: Formatted as `ServicesMasterTable` with frozen header (`A2`).

### Sheet 4: `Eligibility Scenarios` (Purple `#7C3AED`)
- **100 1-to-1 Scenarios**: Linked directly to `CIT-0001` through `CIT-0100` and `SCN-0001` through `SCN-0100`.
- **9 Columns**: `citizen_id`, `scenario_id`, `life_event`, `potential_service`, `eligibility_status`, `reason`, `missing_information`, `next_recommended_step`, `official_source_url`.
- **Status Classification**:
  - `POTENTIAL` (83%): Green badge (`#DCFCE7`), citizen meets preliminary criteria.
  - `NEEDS_VERIFICATION` (6%): Amber badge (`#FEF3C7`), requires pending documentation (e.g. CMO disability certificate, land mutation).
  - `NOT_ELIGIBLE` (11%): Red badge (`#FEE2E2`), fails age or income thresholds.
- **Excel Table**: Formatted as `ScenariosMasterTable` with frozen header (`A2`) and clickable official portal hyperlinks.

### Sheet 5: `Demo Guide` (Amber `#D97706`)
- **Interactive Demonstration Workflows**:
  - *Workflow 1: Looking Up a Synthetic Citizen* (Search & Filter by State, Income, or ID).
  - *Workflow 2: Reviewing Potential Government Services* (Multifactorial Eligibility Matching).
  - *Workflow 3: Checking Missing Eligibility Information* (Handling Incomplete Records).
  - *Workflow 4: Demonstrating an Age-Related Life Event* (Turning 18 Milestone — Voter ID Form 6 + Sarathi Licence).
  - *Workflow 5: Demonstrating Super-Senior Health Universal Cover* (Ayushman 70+ Universal Vaya Vandana Card).
  - *Workflow 6: Explaining the Next Application Step* (Action Engine guidance).
  - *Workflow 7: Showing How Official-Source Verification Works* (Audit trails & NIC ground-truth checking).
- **Backend Integration Patterns**: FastAPI / Pandas loading and PostgreSQL `COPY` syntax.
- **Safety Architecture**: Multi-layer telephony guards preventing real-world dialing.
- **Migration Roadmap**: DPDP Act 2023 compliance, TRAI 140-series CLI allocation, and DLT templates.

### Sheet 6: `Data Dictionary` (Slate Gray `#4B5563`)
- **Exhaustive Schema Documentation**: 76 attributes across all primary and auxiliary sheets:
  - `Citizens` (32 attributes)
  - `Government Services` (10 attributes)
  - `Eligibility Scenarios` (9 attributes)
  - `Validation Report` (9 attributes)
  - `Source Inventory` (8 attributes)
  - `Dashboard` (5 attributes)
  - `Demo Guide` (3 attributes)
- **10 Columns per Entry**: `sheet_name`, `field_name`, `description`, `data_type`, `example_value`, `required`, `allowed_values`, `source_or_origin`, `validation_rule`, `notes`.
- **Excel Table**: Formatted as `DictionaryMasterTable` with frozen header (`A2`).

### Sheet 7: `Validation Report` (Emerald Green `#16A34A`)
- **29 Automated Integrity Checks**: Executed directly against the in-memory and output data:
  - *Structural Integrity*: Record counts (100 citizens, 18 services, 100 scenarios).
  - *Uniqueness & Keys*: Citizen ID, Service ID, Scenario ID uniqueness.
  - *Data Completeness*: Zero null/missing values across 32 mandatory fields.
  - *Safety & Privacy Invariants*: Non-dialable phones (`DEMO-PHONE-xxxx`), safe emails (`@example.com`), `demo_only=TRUE`, zero real Aadhaar / PAN / MSISDN PII.
  - *Mathematical Consistency*: Solar-year age calculation matching DOB relative to reference date (`2026-10-27`), senior citizen logic (`senior == age >= 60`), income bounds.
  - *Relational Integrity*: 0 orphan scenarios, 100% scenario-to-citizen linkage, 100% scenario-to-service linkage, 100% citizen token validity.
  - *Domain & Policy Compliance*: 100% of URLs point to official `.gov.in` or `.nic.in` domains.
  - *Cross-Export Parity & Provenance*: Exact match with legacy exports and SHA-256 duplicate grouping.
- **Audit Outcome**: **29 / 29 Checks PASSED (100%)**, zero errors, zero warnings.
- **Excel Table**: Formatted as `ValidationMasterTable` with frozen header (`A2`).

### Sheet 8: `Source Inventory` (Indigo `#6366F1`)
- **Provenance Audit**: 20 repository artifacts catalogued with cryptographic SHA-256 digests.
- **Duplicate Tracking**: Detects byte-identical redundant exports:
  - `DUP-GROUP-01`: Identical `Timbre_Fake_Citizens.xlsx` files across repository locations.
  - `DUP-GROUP-02`: Identical `Timbre_Fake_Citizens.csv` files across repository locations.
  - `UNIQUE`: Distinct generator scripts, models, and architectural specifications.
- **Excel Table**: Formatted as `InventoryMasterTable` with frozen header (`A2`).

---

## How to Regenerate the Workbook

The master workbook is generated deterministically by the reusable Python generator script:

```bash
# From repository root:
python3 scripts/generate_timbre_master_excel.py

# Or from within FakeData/:
python3 scripts/generate_timbre_master_excel.py
```

### Command-Line Arguments

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--output` / `-o` | `<path>` | Custom destination path for the generated Excel file. | `data/demo/Timbre_Master_Dataset.xlsx` |
| `--no-csv` | *flag* | Suppress generation of companion CSV export files. | `False` (CSVs are exported by default) |
| `--verify-only` | *flag* | Run verification assertions on existing output without regenerating. | `False` |
| `--help` / `-h` | *flag* | Display script usage help and CLI flags. | N/A |

### Example Usages

```bash
# 1. Standard regeneration (Master Excel + 3 Companion CSVs)
python3 scripts/generate_timbre_master_excel.py

# 2. Re-verify existing output workbook using openpyxl assertion suite
python3 scripts/generate_timbre_master_excel.py --verify-only

# 3. Custom output destination
python3 scripts/generate_timbre_master_excel.py --output /tmp/Custom_Timbre_Dataset.xlsx
```

---

## Safety & Invariant Guarantees

1. **100% Fictional Data**: Every synthetic citizen profile is procedurally generated with no connection to living individuals (DPDP Act 2023 Section 2(t) compliant).
2. **Non-Dialable Telephony**: All phone numbers strictly follow the pattern `DEMO-PHONE-xxxx`. Standard telecommunications switches (ITU-T E.164) and SIP trunk providers cannot route non-numeric alphabetic strings.
3. **Domain Isolation**: All email addresses strictly end in `@example.com` (reserved under RFC 2606 for documentation and testing).
4. **Boolean Gatekeeper**: Every record contains `demo_only = TRUE`. The Timbre telephony and backend adapters halt execution if any record with `demo_only != TRUE` is encountered.
5. **No Secret Leakage**: Zero API keys, passwords, database credentials, or environment secrets are present in any dataset or script.
