import csv
import json
import os
from datetime import date
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

REFERENCE_DATE = date(2026, 10, 28)

STATES_DATA = [
    {"state": "Uttar Pradesh", "district": "Varanasi", "city": "Kashi", "rural_urban": "URBAN", "lang": "Hindi", "pin": "221001"},
    {"state": "Uttar Pradesh", "district": "Gorakhpur", "city": "Pipraich Village", "rural_urban": "RURAL", "lang": "Hindi", "pin": "273152"},
    {"state": "Maharashtra", "district": "Pune", "city": "Haveli Village", "rural_urban": "RURAL", "lang": "Marathi", "pin": "412207"},
    {"state": "Maharashtra", "district": "Nagpur", "city": "Nagpur City", "rural_urban": "URBAN", "lang": "Marathi", "pin": "440001"},
    {"state": "Bihar", "district": "Patna", "city": "Danapur", "rural_urban": "URBAN", "lang": "Hindi", "pin": "801503"},
    {"state": "Bihar", "district": "Muzaffarpur", "city": "Saraiya Village", "rural_urban": "RURAL", "lang": "Hindi", "pin": "843126"},
    {"state": "Rajasthan", "district": "Jaipur", "city": "Chaksu Village", "rural_urban": "RURAL", "lang": "Hindi", "pin": "303901"},
    {"state": "Rajasthan", "district": "Jodhpur", "city": "Jodhpur City", "rural_urban": "URBAN", "lang": "Hindi", "pin": "342001"},
    {"state": "Madhya Pradesh", "district": "Indore", "city": "Mhow", "rural_urban": "URBAN", "lang": "Hindi", "pin": "453441"},
    {"state": "Madhya Pradesh", "district": "Sehore", "city": "Ashta Village", "rural_urban": "RURAL", "lang": "Hindi", "pin": "466116"},
    {"state": "Karnataka", "district": "Bengaluru Rural", "city": "Doddaballapura", "rural_urban": "RURAL", "lang": "Kannada", "pin": "561203"},
    {"state": "Karnataka", "district": "Mysuru", "city": "Mysuru City", "rural_urban": "URBAN", "lang": "Kannada", "pin": "570001"},
    {"state": "Tamil Nadu", "district": "Coimbatore", "city": "Pollachi", "rural_urban": "RURAL", "lang": "Tamil", "pin": "642001"},
    {"state": "Tamil Nadu", "district": "Madurai", "city": "Madurai City", "rural_urban": "URBAN", "lang": "Tamil", "pin": "625001"},
    {"state": "Gujarat", "district": "Anand", "city": "Petlad Village", "rural_urban": "RURAL", "lang": "Gujarati", "pin": "388450"},
    {"state": "Gujarat", "district": "Surat", "city": "Surat City", "rural_urban": "URBAN", "lang": "Gujarati", "pin": "395001"},
    {"state": "West Bengal", "district": "Hooghly", "city": "Singur Village", "rural_urban": "RURAL", "lang": "Bengali", "pin": "712409"},
    {"state": "West Bengal", "district": "Kolkata", "city": "Kolkata Central", "rural_urban": "URBAN", "lang": "Bengali", "pin": "700001"},
    {"state": "Punjab", "district": "Ludhiana", "city": "Jagraon Village", "rural_urban": "RURAL", "lang": "Punjabi", "pin": "142026"},
    {"state": "Telangana", "district": "Warangal", "city": "Hanamkonda", "rural_urban": "URBAN", "lang": "Telugu", "pin": "506001"}
]

NAMES_POOL = [
    ("Aarav", "Sharma", "MALE"), ("Priya", "Patel", "FEMALE"), ("Rohan", "Verma", "MALE"), ("Ananya", "Deshmukh", "FEMALE"),
    ("Vikram", "Singh", "MALE"), ("Sneha", "Kumar", "FEMALE"), ("Aditya", "Joshi", "MALE"), ("Pooja", "Mehta", "FEMALE"),
    ("Rahul", "Yadav", "MALE"), ("Kavita", "Chauhan", "FEMALE"), ("Amit", "Gupta", "MALE"), ("Sunita", "Mishra", "FEMALE"),
    ("Suresh", "Patil", "MALE"), ("Meera", "Reddy", "FEMALE"), ("Manoj", "Tiwari", "MALE"), ("Divya", "Nair", "FEMALE"),
    ("Deepak", "Choudhary", "MALE"), ("Ritu", "Bose", "FEMALE"), ("Rajesh", "Kaur", "MALE"), ("Shweta", "Rao", "FEMALE")
]

LIFE_EVENTS = [
    {
        "event": "Approaching age 18",
        "age": 17,
        "dob_offset_years": 17,
        "dob_month": 11,
        "dob_day": 15,
        "is_student": True,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "High School Student",
        "education": "Higher Secondary Student",
        "employment": "Student",
        "income": 140000,
        "bracket": "LOW",
        "services": ["SVC-VOTER-ID", "SVC-LEARNER-LICENCE", "SVC-PAN-CARD"],
        "notes": "Turning 18 next month; eligible for advance ECI Form 6 voter enrollment and learner's driving licence.",
        "docs": ["Birth Certificate", "10th Marksheet", "Aadhaar Card", "Passport Photo"]
    },
    {
        "event": "Approaching age 18",
        "age": 18,
        "dob_offset_years": 18,
        "dob_month": 10,
        "dob_day": 20,
        "is_student": True,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "College Fresher",
        "education": "12th Pass",
        "employment": "Student",
        "income": 120000,
        "bracket": "LOW",
        "services": ["SVC-VOTER-ID", "SVC-LEARNER-LICENCE", "SVC-PAN-CARD", "SVC-NSP-SCHOLARSHIP"],
        "notes": "Attained statutory majority (age 18); immediately eligible for Voter ID Form 6, Parivahan Driving Licence, and NSP scholarships.",
        "docs": ["Aadhaar Card", "Class 10 Certificate", "College Bonafide", "Residence Proof"]
    },
    {
        "event": "Starting college",
        "age": 19,
        "dob_offset_years": 19,
        "dob_month": 6,
        "dob_day": 10,
        "is_student": True,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Undergraduate Student",
        "education": "Pursuing B.Sc / B.Tech",
        "employment": "Student",
        "income": 160000,
        "bracket": "LOW",
        "services": ["SVC-NSP-SCHOLARSHIP", "SVC-PAN-CARD", "SVC-VOTER-ID"],
        "notes": "Starting higher education; seeking post-matric merit-cum-means scholarship on National Scholarship Portal.",
        "docs": ["College ID / Admission Slip", "12th Marksheet", "Income Certificate", "Bank Account Details"]
    },
    {
        "event": "Seeking employment",
        "age": 23,
        "dob_offset_years": 23,
        "dob_month": 4,
        "dob_day": 5,
        "is_student": False,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Job Seeker / Freelance Trainee",
        "education": "Graduate",
        "employment": "Unemployed / Looking for Work",
        "income": 95000,
        "bracket": "BPL",
        "services": ["SVC-E-SHRAM", "SVC-PAN-CARD", "SVC-AYUSHMAN-BHARAT"],
        "notes": "Entering job market; needs PAN Card for employment onboarding and e-Shram / skill database registration.",
        "docs": ["Degree Certificate", "Aadhaar Card", "PAN Application Form", "Bank Passbook"]
    },
    {
        "event": "Getting married",
        "age": 26,
        "dob_offset_years": 26,
        "dob_month": 8,
        "dob_day": 18,
        "is_student": False,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Junior Accountant / Clerk",
        "education": "B.Com",
        "employment": "Employed (Private Sector)",
        "income": 320000,
        "bracket": "MIDDLE",
        "services": ["SVC-VOTER-ID", "SVC-PAN-CARD"],
        "notes": "Upcoming marriage; exploring spousal address update on voter list and joint banking PAN procedures.",
        "docs": ["Aadhaar Card", "Current Address Proof", "Marriage Certificate / Wedding Card"]
    },
    {
        "event": "Having a child",
        "age": 30,
        "dob_offset_years": 30,
        "dob_month": 3,
        "dob_day": 12,
        "is_student": False,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Small Shopkeeper",
        "education": "12th Pass",
        "employment": "Self-Employed",
        "income": 210000,
        "bracket": "LOW",
        "services": ["SVC-SUKANYA-SAMRIDDHI", "SVC-AYUSHMAN-BHARAT"],
        "notes": "Welcomed newborn daughter; eligible to open Sukanya Samriddhi Yojana (SSA) high-yield savings account.",
        "docs": ["Child Hospital Birth Certificate", "Parent Aadhaar", "Parent PAN Card", "Passport Photos"]
    },
    {
        "event": "Exploring farmer services",
        "age": 42,
        "dob_offset_years": 42,
        "dob_month": 1,
        "dob_day": 25,
        "is_student": False,
        "is_farmer": True,
        "is_senior": False,
        "occupation": "Smallholder Farmer",
        "education": "10th Pass",
        "employment": "Self-Employed (Agriculture)",
        "income": 110000,
        "bracket": "LOW",
        "services": ["SVC-PM-KISAN", "SVC-AYUSHMAN-BHARAT", "SVC-E-SHRAM"],
        "notes": "Cultivating 1.8 acres inherited land; seeking PM-KISAN INR 6,000 annual installment income support.",
        "docs": ["Khasra/Khatauni Land Record", "Aadhaar Card", "Bank Passbook with Aadhaar Seeding"]
    },
    {
        "event": "Becoming a senior citizen",
        "age": 60,
        "dob_offset_years": 60,
        "dob_month": 10,
        "dob_day": 1,
        "is_student": False,
        "is_farmer": False,
        "is_senior": True,
        "occupation": "Retired Labourer",
        "education": "Primary School",
        "employment": "Retired",
        "income": 72000,
        "bracket": "BPL",
        "services": ["SVC-IGNOAPS-PENSION", "SVC-AYUSHMAN-BHARAT"],
        "notes": "Turned 60 years of age on 1st October; eligible for IGNOAPS monthly pension and Ayushman Bharat senior cover.",
        "docs": ["Age Proof (Aadhaar / Voter ID)", "BPL Ration Card", "Post Office Savings Passbook"]
    },
    {
        "event": "Exploring certificates and scholarships",
        "age": 20,
        "dob_offset_years": 20,
        "dob_month": 5,
        "dob_day": 14,
        "is_student": True,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Diploma Polytechnic Student",
        "education": "Pursuing Polytechnic",
        "employment": "Student",
        "income": 90000,
        "bracket": "BPL",
        "services": ["SVC-NSP-SCHOLARSHIP", "SVC-PAN-CARD"],
        "notes": "Low income polytechnic student applying for state technical education fee reimbursement scholarship.",
        "docs": ["Income Certificate from Tehsildar", "Bonafide Certificate", "Marksheet", "Aadhaar Card"]
    },
    {
        "event": "Exploring disability-related services",
        "age": 35,
        "dob_offset_years": 35,
        "dob_month": 9,
        "dob_day": 30,
        "is_student": False,
        "is_farmer": False,
        "is_senior": False,
        "occupation": "Handicraft Artisan",
        "education": "10th Pass",
        "employment": "Self-Employed",
        "income": 130000,
        "bracket": "LOW",
        "services": ["SVC-UDID-DISABILITY", "SVC-AYUSHMAN-BHARAT"],
        "notes": "Applying for Swavlamban UDID card with district medical board 45% locomotor evaluation certificate.",
        "docs": ["Medical Board Disability Certificate", "Aadhaar Card", "Address Proof", "Photo"]
    }
]


def generate_citizens_records():
    records = []
    num_events = len(LIFE_EVENTS)
    num_states = len(STATES_DATA)
    num_names = len(NAMES_POOL)

    for i in range(1, 101):
        citizen_id = f"CIT-{i:04d}"
        event_cfg = LIFE_EVENTS[(i - 1) % num_events]
        state_cfg = STATES_DATA[(i - 1) % num_states]
        name_cfg = NAMES_POOL[(i - 1) % num_names]

        target_age = event_cfg["age"]
        dob_m = event_cfg["dob_month"]
        dob_d = event_cfg["dob_day"]
        if (REFERENCE_DATE.month, REFERENCE_DATE.day) < (dob_m, dob_d):
            birth_year = REFERENCE_DATE.year - target_age - 1
        else:
            birth_year = REFERENCE_DATE.year - target_age

        dob = date(birth_year, dob_m, dob_d)
        
        # Verify deterministic age
        cal_age = REFERENCE_DATE.year - dob.year
        if (REFERENCE_DATE.month, REFERENCE_DATE.day) < (dob.month, dob.day):
            cal_age -= 1
        assert cal_age == target_age, f"Mismatch for {citizen_id}: {cal_age} != {target_age}"

        first_name = name_cfg[0]
        # Make name unique if needed
        last_name = f"{name_cfg[1]}-{i}" if i > 20 else name_cfg[1]
        full_name = f"{first_name} {last_name}"
        gender = name_cfg[2]

        family_size = 3 + (i % 4)
        has_child = 1 if (event_cfg["age"] >= 25 and i % 2 == 0) else (2 if event_cfg["event"] == "Having a child" else 0)
        marital = "Married" if (event_cfg["age"] >= 25 and i % 3 != 0) else "Single"
        if event_cfg["age"] >= 60 and i % 5 == 0:
            marital = "Widowed"

        record = {
            "citizen_id": citizen_id,
            "id": citizen_id,
            "first_name": first_name,
            "last_name": last_name,
            "name": full_name,
            "date_of_birth": dob.isoformat(),
            "age": cal_age,
            "gender": gender,
            "state": state_cfg["state"],
            "district": state_cfg["district"],
            "city_or_village": state_cfg["city"],
            "rural_or_urban": state_cfg["rural_urban"],
            "preferred_language": state_cfg["lang"],
            "education": event_cfg["education"],
            "occupation": event_cfg["occupation"],
            "employment_status": event_cfg["employment"],
            "synthetic_family_income": event_cfg["income"] + (i * 500),
            "simulated_income_bracket": event_cfg["bracket"],
            "family_size": family_size,
            "marital_status": marital,
            "children": has_child,
            "is_student": event_cfg["is_student"],
            "is_farmer": event_cfg["is_farmer"],
            "is_senior_citizen": event_cfg["is_senior"] or cal_age >= 60,
            "simulated_life_event": event_cfg["event"],
            "potentially_relevant_services": json.dumps(event_cfg["services"]),
            "eligibility_notes": event_cfg["notes"],
            "required_documents": json.dumps(event_cfg["docs"]),
            "demo_only": True,
            "phone_number": f"DEMO-PHONE-{i:04d}",
            "email": f"cit{i:04d}@example.com",
            "pincode": state_cfg["pin"]
        }
        records.append(record)
    
    assert len(records) == 100, f"Expected exactly 100 records, got {len(records)}"
    return records


def write_csv(records, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys())
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)
    print(f"Wrote {len(records)} records to CSV: {output_path}")


def write_excel(records, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()

    # Sheet 1: Safety Notice & Disclaimer
    ws_notice = wb.active
    ws_notice.title = "DEMO_SAFETY_WARNING"
    ws_notice.views.sheetView[0].showGridLines = True

    title_fill = PatternFill(start_color="FFE5E5", end_color="FFE5E5", fill_type="solid")
    title_font = Font(name="Calibri", size=14, bold=True, color="990000")
    body_font = Font(name="Calibri", size=11, color="1A1A1A")
    bullet_font = Font(name="Calibri", size=11, bold=True, color="333333")

    ws_notice["A1"] = "⚠️ TIMBRE PROTOTYPE: MANDATORY SYNTHETIC DATA SAFEGUARD NOTICE"
    ws_notice["A1"].font = title_font
    ws_notice["A1"].fill = title_fill
    ws_notice.merge_cells("A1:G1")

    notices = [
        ("Reference Date", f"{REFERENCE_DATE.isoformat()} (All citizen ages and life milestones calibrated to this date)"),
        ("Synthetic Status", "100% FICTIONAL SYNTHETIC DEMONSTRATION RECORDS (CIT-0001 through CIT-0100)"),
        ("No Real PII", "NO real Indian citizens, Aadhaar, PAN, voter ID numbers, or bank accounts are contained herein."),
        ("Non-Dialable Phone", "All telephone fields use non-dialable placeholders (DEMO-PHONE-xxxx). Never contact anyone."),
        ("Fictional Email", "All email addresses use the reserved RFC 2606 example.com domain."),
        ("Demo Only Guard", "demo_only=TRUE is strictly asserted on all records across memory, CSV, and SQLite."),
        ("Prototype Purpose", "Built exclusively for the Timbre Government-Services Voice Assistant Buildathon.")
    ]

    for idx, (label, text) in enumerate(notices, start=3):
        ws_notice[f"A{idx}"] = label
        ws_notice[f"A{idx}"].font = bullet_font
        ws_notice[f"B{idx}"] = text
        ws_notice[f"B{idx}"].font = body_font

    ws_notice.column_dimensions["A"].width = 24
    ws_notice.column_dimensions["B"].width = 85

    # Sheet 2: Fictional Citizens
    ws_data = wb.create_sheet(title="Fake_Citizens_100")
    ws_data.views.sheetView[0].showGridLines = True

    headers = [
        "citizen_id", "first_name", "last_name", "full_name", "date_of_birth", "age",
        "gender", "state", "district", "city_or_village", "rural_or_urban", "preferred_language",
        "education", "occupation", "employment_status", "synthetic_family_income_inr",
        "simulated_income_bracket", "family_size", "marital_status", "children",
        "is_student", "is_farmer", "is_senior_citizen", "simulated_life_event",
        "potentially_relevant_services", "eligibility_notes", "required_documents",
        "demo_only", "phone_number", "email", "pincode"
    ]

    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)

    for col_num, header in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, r in enumerate(records, start=2):
        row_values = [
            r["citizen_id"], r["first_name"], r["last_name"], r["name"], r["date_of_birth"], r["age"],
            r["gender"], r["state"], r["district"], r["city_or_village"], r["rural_or_urban"], r["preferred_language"],
            r["education"], r["occupation"], r["employment_status"], r["synthetic_family_income"],
            r["simulated_income_bracket"], r["family_size"], r["marital_status"], r["children"],
            r["is_student"], r["is_farmer"], r["is_senior_citizen"], r["simulated_life_event"],
            r["potentially_relevant_services"], r["eligibility_notes"], r["required_documents"],
            r["demo_only"], r["phone_number"], r["email"], r["pincode"]
        ]
        for col_num, val in enumerate(row_values, 1):
            cell = ws_data.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = data_font
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right")
            elif isinstance(val, bool):
                cell.alignment = Alignment(horizontal="center")

    for col in ws_data.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_data.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    wb.save(output_path)
    print(f"Wrote {len(records)} records to Excel: {output_path}")


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = repo_root / "data" / "demo"
    csv_path = data_dir / "Timbre_Fake_Citizens.csv"
    xlsx_path = data_dir / "Timbre_Fake_Citizens.xlsx"

    records = generate_citizens_records()
    write_csv(records, csv_path)
    write_excel(records, xlsx_path)
    print(f"Successfully generated 100 fictional citizens calibrated to reference date {REFERENCE_DATE}.")


if __name__ == "__main__":
    main()
