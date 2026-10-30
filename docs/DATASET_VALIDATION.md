# Synthetic dataset validation

Source files are preserved at `data/demo/Timbre_Fake_Citizens.csv` and `.xlsx`. Run the repeatable aggregate validation from the backend directory:

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.validate_dataset
```

The script writes `data/reports/dataset_validation.json`. It does not emit record values or alter the input dataset. It checks schema presence, field types, identifier format/duplicates, DOB and age consistency against `REFERENCE_DATE`, synthetic markers and placeholder contacts, sensitive-looking values/secrets, JSON list fields, service codes, CSV/XLSX row and column compatibility, and HTTPS government source URL shape.

Current validation: **PASS**, 100 CSV records, 32 CSV columns, 100 workbook records, no duplicate IDs, 0 validation errors. The workbook uses three documented equivalent column aliases (`id`/`citizen_id`, `full_name`/`name`, and `synthetic_family_income_inr`/`synthetic_family_income`). The report contains 11 warnings: all 10 service catalogue entries need a human source review, and factual rule content is not validated by checking URL domains. Marker checks support the dataset's synthetic labeling, but cannot independently prove how a source dataset was created.

The backend now passes a minimal synthetic profile context to chat: calculated age at the configured reference date, state, education/occupation, income band, and eligibility flags. It excludes names, record IDs, email, phone, and exact income. Only matching service entries are considered; unrelated questions no longer pull in arbitrary records. Missing profile values are explicitly treated as unknown. All catalogue entries are marked `NEEDS_REVIEW` until a human checks eligibility, documents, fees, deadlines, and source URLs. The model is instructed to avoid factual claims from pending entries; this is a prompt-level control, not a formal guarantee.

Official-source spot checks found:

- ECI's current voter FAQ describes four qualifying dates and Form 6: [ECI voter registration FAQ](https://www.eci.gov.in/faq/en/how-to-register).
- PM-KISAN's official page describes landholding farmer families and exclusion categories: [PM-KISAN scheme](https://pmkisan.gov.in/homenew.aspx).
- NHA's senior-citizen FAQ states 70+ eligibility regardless of economic status: [NHA PM-JAY FAQ](https://nha.gov.in/img/resources/English_FAQs_related_to_the_benefits_for_senior_citizens.pdf).
- India Post describes SSA eligibility for girls below 10 and guardian-opened accounts: [India Post savings schemes](https://www.indiapost.gov.in/banking-services/savings).
- NSP publishes scheme-specific criteria and deadlines, so one generic student income ceiling should not be applied across schemes: [National Scholarship Portal FAQ](https://scholarships.gov.in/faq) and [current scheme list](https://scholarships.gov.in/All-Scholarships).

These spot checks do not constitute a full review of all 10 schemes or their fees/documents. Pending entries remain marked as such in the app and AI context.
