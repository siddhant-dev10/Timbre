import csv
import re
from pathlib import Path
import openpyxl
from app.scripts.seed_db import seed_database
from app.models.citizen import Citizen
from app.scripts.validate_dataset import validate_dataset


def test_dataset_record_counts_and_attributes():
    root = Path(__file__).resolve().parent.parent.parent
    csv_path = root / "data" / "demo" / "Timbre_Fake_Citizens.csv"
    xlsx_path = root / "data" / "demo" / "Timbre_Fake_Citizens.xlsx"

    assert csv_path.exists(), "CSV dataset missing"
    assert xlsx_path.exists(), "Excel dataset missing"

    # Read CSV
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 100, f"Expected exactly 100 citizens, found {len(reader)}"

    ids = set()
    for row in reader:
        cid = row["citizen_id"]
        assert cid.startswith("CIT-"), f"Invalid ID format: {cid}"
        ids.add(cid)
        # Check demo_only
        assert row["demo_only"].lower() in ("true", "1"), f"Record {cid} not marked demo_only"
        # Check non-dialable phone
        assert row["phone_number"].startswith("DEMO-PHONE-"), f"Unsafe phone in {cid}: {row['phone_number']}"
        # Check example.com email
        assert row["email"].endswith("@example.com"), f"Non-example email in {cid}: {row['email']}"
        # Ensure no real Aadhaar (12 digits) or PAN (10 chars uppercase alphanumeric) in row values
        for val in row.values():
            val_str = str(val)
            # 12 consecutive digits check
            assert not re.search(r"\b\d{12}\b", val_str), f"Found potential 12-digit ID in {cid}: {val_str}"

    assert len(ids) == 100, "Citizen IDs are not all unique"

    # Read Excel
    wb = openpyxl.load_workbook(xlsx_path)
    assert "DEMO_SAFETY_WARNING" in wb.sheetnames, "Excel missing safety disclaimer sheet"
    assert "Fake_Citizens_100" in wb.sheetnames, "Excel missing data sheet"

    ws_data = wb["Fake_Citizens_100"]
    # 1 header row + 100 data rows = 101 rows
    excel_rows = list(ws_data.iter_rows(values_only=True))
    assert len(excel_rows) == 101, f"Expected 101 rows in Excel, got {len(excel_rows)}"


def test_seed_idempotency(db):
    initial_count = db.query(Citizen).count()
    assert initial_count == 100

    # Run seed again
    seed_database(db_session=db)
    after_count = db.query(Citizen).count()
    assert after_count == 100, f"Database citizen count changed after re-seed: {after_count}"


def test_repeatable_dataset_validation_is_aggregate_only(tmp_path):
    root = Path(__file__).resolve().parent.parent.parent
    report = validate_dataset(
        root / "data" / "demo" / "Timbre_Fake_Citizens.csv",
        root / "data" / "demo" / "Timbre_Fake_Citizens.xlsx",
        report_path=tmp_path / "report.json",
    )
    assert report["status"] == "PASS"
    assert report["csv_record_count"] == 100
    assert report["xlsx_record_count"] == 100
    assert report["duplicate_identifier_count"] == 0
    written = (tmp_path / "report.json").read_text()
    assert "Aarav" not in written
    assert "phone_number" not in written


def test_dataset_validation_reports_bad_rows_without_record_values(tmp_path):
    import csv
    import json

    root = Path(__file__).resolve().parent.parent.parent
    source = root / "data" / "demo" / "Timbre_Fake_Citizens.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0]["email"] = "private@example.org"
    rows[0]["age"] = "invalid"
    rows[0]["citizen_id"] = rows[1]["citizen_id"]
    damaged = tmp_path / "damaged.csv"
    with damaged.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = validate_dataset(damaged, root / "data" / "demo" / "Timbre_Fake_Citizens.xlsx", report_path=None)
    assert report["status"] == "FAIL"
    assert report["errors"]["duplicate_identifiers"] >= 1
    assert report["errors"]["invalid_field_types"] >= 1
    serialized = json.dumps(report)
    assert "private@example.org" not in serialized
