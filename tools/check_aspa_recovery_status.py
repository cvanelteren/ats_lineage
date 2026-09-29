"""Check dated legal-effect evidence for the four blocked 2021 revisions.

PDF headers corroborate the assistant's separate official-web-record reading.
This checker does not validate provisions or download/recheck live legal status.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/breakdown_review"


def parse_header(page: str) -> dict:
    # Restrict status parsing to the header: operative text can cite earlier
    # instruments and dates which must not supply this instrument's identity.
    header = page.split("Meeting", 1)[0]
    identity = re.search(
        r"\AMEASURE\s+ANTARCTIC SPECIALLY PROTECTED AREA NO\s+"
        r"(\d+)\s+\((\d{4})\)\s+(\d+)\b",
        header,
    )
    status = re.search(r"\bEFFECTIVE (\d{2}-\d{2}-\d{4}) \((FAST APPROVAL)\)", header)
    if not identity or not status:
        raise ValueError("missing or unsupported ASPA Measure header/status")
    return {
        "instrument_type": "Measure",
        "number": int(identity[1]),
        "year": int(identity[2]),
        "aspa": int(identity[3]),
        "effective_date": datetime.strptime(status[1], "%d-%m-%Y").date().isoformat(),
        "approval_route": "Fast Approval",
    }


def validate_records(meta: dict, cohort: dict, pages: list[str]) -> dict:
    expected = {
        (p["aspa"], "Measure", p["followup"]["measure"], p["followup"]["year"])
        for p in cohort["plans"]
        if p["disposition"] == "cep_no_consensus"
    }
    identities = [
        (r["aspa"], r["instrument_type"], r["number"], r["year"])
        for r in meta["records"]
    ]
    if len(set(identities)) != len(identities) or set(identities) != expected:
        raise ValueError("status records do not match the blocked cohort follow-up")
    discrepancies = []
    for record in meta["records"]:
        page = pages[record["pdf_page"] - 1]
        parsed = parse_header(page)
        if any(record[key] != value for key, value in parsed.items()):
            raise ValueError("coded record does not match original PDF header")
        body_area = re.search(
            r"\nMeasure\s+Antarctic Specially Protected Area No (\d+)\b", page
        )
        if not body_area or int(body_area[1]) != record["export_body_area"]:
            raise ValueError("unexpected export body identity")
        if int(body_area[1]) != record["aspa"]:
            if not record.get("export_discrepancy"):
                raise ValueError("undocumented header/body mismatch")
            discrepancies.append(record["aspa"])
    return {
        "followed_blocked_revisions": len(identities),
        "entered_into_force": len(identities),
        "effective_dates": sorted({r["effective_date"] for r in meta["records"]}),
        "export_body_discrepancies": discrepancies,
        "retained_disputed_provisions": None,
        "implementation_assessed": False,
        "check_scope": "Archived headers and cohort identities; no automated verification of live pages or provision retention.",
    }


def build() -> dict:
    meta = json.loads((DATA / "aspa_recovery_status.json").read_text())
    cohort = json.loads((DATA / "aspa_2021_cohort.json").read_text())
    pdf = ROOT / meta["source_file"]
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != meta["source_sha256"]:
        raise ValueError("source PDF hash mismatch")
    raw = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
    return validate_records(meta, cohort, raw.split("\f"))


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
