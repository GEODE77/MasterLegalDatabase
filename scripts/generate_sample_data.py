"""Generate realistic sample Colorado bill data for pipeline testing.

Generates realistic sample Colorado bill data for pipeline testing. Produces
extracted text JSONs that mimic real bill output so every pipeline stage can be
validated without downloading actual bills.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Sequence

PAGE_BREAK = "\n\n---PAGE BREAK---\n\n"
SECTION_SYMBOL = "\u00a7"
DEFAULT_SAMPLE_DIR = "data/sample"
DEFAULT_PIPELINE_SEED_DIR = "data/extracted_text"
GENERATOR_VERSION = "1.0.0"
LINES_PER_PAGE = 50

SAMPLE_BILLS: list[dict[str, Any]] = [
    {
        "bill_number": "HB25-1001",
        "title": "CONCERNING THE REGULATION OF EMISSIONS FROM INDUSTRIAL FACILITIES",
        "house_sponsors": ["Smith", "Garcia", "Thompson"],
        "senate_sponsors": ["Williams"],
        "committee": "Energy & Environment",
        "domain": "Environmental / Manufacturing",
        "summary_lines": [
            "The bill requires industrial facilities to monitor air emissions.",
            "The bill creates water quality reporting for industrial discharges.",
            "The bill funds implementation through the General Fund.",
        ],
        "sections": [
            {
                "number": 1,
                "lead": f"{SECTION_SYMBOL} 25-7-114.7, C.R.S., is amended to read:",
                "body": [
                    "(1) The division shall establish emission monitoring requirements.",
                    "(2) Each covered industrial facility shall report emissions quarterly.",
                    "(3) As used in this section:",
                    "(a) 'stationary source' means a building, structure, facility, or installation that emits or may emit an air pollutant.",
                    "(b) 'industrial facility' means a manufacturing, processing, mining, or energy facility subject to a permit.",
                    "(4) A facility shall retain monitoring records for at least five years.",
                    "(5) The commission shall adopt rules in accordance with \u00a7 24-4-103, C.R.S.",
                    "(6) The House Energy & Environment Committee reviewed the industrial emissions reporting schedule.",
                    "(7) A person who knowingly falsifies an emissions report commits a class 1 misdemeanor.",
                    "(8) A civil penalty of $10,000 may be imposed for a willful violation.",
                ],
            },
            {
                "number": 2,
                "lead": f"{SECTION_SYMBOL} 25-7-114.8, C.R.S., is amended to read:",
                "body": [
                    "(1) The industrial emissions compliance fund is created in the state treasury.",
                    "(2) The fund consists of fees, gifts, grants, and $2,500,000 transferred for the 2025-26 fiscal year.",
                    "(3) Money in the fund is continuously appropriated to the division.",
                    "(4) The division may use the fund for permitting, inspection, and technical assistance.",
                    "(5) A facility shall submit a compliance plan by July 1, 2025.",
                    "(6) The division shall publish annual reports on emission reductions and enforcement outcomes.",
                ],
            },
            {
                "number": 3,
                "lead": f"{SECTION_SYMBOL} 25-8-205, C.R.S., is amended BY THE ADDITION OF A NEW SUBSECTION to read:",
                "body": [
                    "(7) A permit for an industrial discharge must include monitoring conditions for water quality impacts.",
                    "(8) The division shall coordinate air quality and water quality inspections for industrial facilities.",
                    "(9) The division may require electronic reporting for discharge monitoring results.",
                    "(10) For the 2025-26 state fiscal year, $500,000 is appropriated from the General Fund to the department of public health and environment.",
                    "(11) The appropriation is for implementation of this act and related information technology costs.",
                ],
            },
            {
                "number": 4,
                "heading": "Effective date.",
                "body": ["This act takes effect July 1, 2025."],
            },
        ],
    },
    {
        "bill_number": "SB25-0055",
        "title": "CONCERNING MODIFICATIONS TO THE COLORADO WAGE EQUITY ACT",
        "house_sponsors": ["Chen", "Adams"],
        "senate_sponsors": ["Johnson", "Rivera"],
        "committee": "Business Affairs & Labor",
        "domain": "Labor / Employment",
        "summary_lines": [
            "The bill updates wage transparency requirements.",
            "The bill clarifies employer recordkeeping obligations.",
            "The bill applies broadly to Colorado employers.",
        ],
        "sections": [
            {
                "number": 1,
                "lead": f"{SECTION_SYMBOL} 8-6-101, C.R.S., is amended to read:",
                "body": [
                    "(1) As used in this section:",
                    "(a) 'employer' means a person, firm, partnership, association, corporation, receiver, or other officer of a court of this state that employs a person in Colorado.",
                    "(b) 'wage rate' means all compensation promised or paid for labor or services.",
                    "(2) An employer shall provide written notice of wage ranges and benefits.",
                    "(3) The director shall publish wage transparency guidance for the 2025-26 fiscal year.",
                    "(4) The House Business Affairs & Labor Committee may request annual compliance data.",
                    "(5) The division may investigate a complaint filed by an employee or applicant.",
                    "(6) Records required by this section must be retained for three years.",
                ],
            },
            {
                "number": 2,
                "lead": f"{SECTION_SYMBOL} 8-13.5-201, C.R.S., is amended to read:",
                "body": [
                    "(1) An employer shall maintain records showing wage rates, job descriptions, and promotion opportunities.",
                    "(2) An employer shall not retaliate against an employee who requests wage information.",
                    "(3) The division may issue a civil penalty of $5,000 for each willful violation.",
                    "(4) The director may adopt rules to implement this section.",
                    "(5) The rules must be consistent with article 6 of this title 8.",
                ],
            },
            {
                "number": 3,
                "heading": "Effective date.",
                "body": ["This act takes effect upon passage."],
            },
        ],
    },
    {
        "bill_number": "HB25-1042",
        "title": "CONCERNING REQUIREMENTS FOR HEALTH INSURANCE COVERAGE OF BEHAVIORAL HEALTH SERVICES",
        "house_sponsors": ["Martinez", "Lee"],
        "senate_sponsors": ["Patel"],
        "committee": "Health & Insurance",
        "domain": "Healthcare / Insurance",
        "summary_lines": [
            "The bill requires coverage for behavioral health services.",
            "The bill aligns Medicaid and commercial health insurance standards.",
            "The bill funds implementation and staffing.",
        ],
        "sections": [
            {
                "number": 1,
                "lead": f"{SECTION_SYMBOL} 10-16-104, C.R.S., is amended to read:",
                "body": [
                    "(1) A carrier that offers a health benefit plan shall provide coverage for behavioral health services on terms no more restrictive than medical services.",
                    "(2) The House Health & Insurance Committee shall receive an annual parity compliance report.",
                    "(3) As used in this section:",
                    "(a) 'behavioral health disorder' means a mental health or substance use disorder that is recognized in current clinical standards.",
                    "(b) 'parity' means coverage requirements that are comparable for behavioral health and medical benefits.",
                    "(4) A carrier shall submit network adequacy data to the commissioner.",
                    "(5) A carrier shall provide notice of appeal rights to a patient after an adverse determination.",
                ],
            },
            {
                "number": 2,
                "lead": f"{SECTION_SYMBOL} 25.5-5-402, C.R.S., is amended to read:",
                "body": [
                    "(1) The state department shall seek federal approval to align medicaid managed care contracts with behavioral health parity requirements.",
                    "(2) The department may use 2.0 FTE to implement this section.",
                    "(3) The department shall report implementation costs by November 1, 2025.",
                    "(4) The report must identify any necessary federal waiver amendments.",
                ],
            },
            {
                "number": 3,
                "lead": f"{SECTION_SYMBOL} 27-60-104, C.R.S., is amended to read:",
                "body": [
                    "(1) The behavioral health administration shall coordinate provider standards for clinical services and patient access.",
                    "(2) The administration shall consult with carriers, hospitals, patients, and licensed professionals.",
                    "(3) The administration may publish guidance on clinical best practices.",
                ],
            },
            {
                "number": 4,
                "lead": f"{SECTION_SYMBOL} 10-16-104.5, C.R.S., is added to read:",
                "body": [
                    "(1) A carrier shall maintain an internal appeal process for a denial of behavioral health services.",
                    "(2) For the 2025-26 state fiscal year, $1,200,000 is appropriated from the Healthcare Affordability Fund to the division of insurance.",
                    "(3) The appropriation includes spending authority for 2.0 FTE.",
                    "(4) Money appropriated in this section remains available through June 30, 2026.",
                ],
            },
            {
                "number": 5,
                "heading": "Effective date.",
                "body": ["This act takes effect January 1, 2026."],
            },
        ],
    },
    {
        "bill_number": "SB25-0123",
        "title": "CONCERNING UPDATES TO MINED LAND RECLAMATION REQUIREMENTS",
        "house_sponsors": ["Baker", "Wilson"],
        "senate_sponsors": ["Ortega"],
        "committee": "Agriculture & Natural Resources",
        "domain": "Mining / Natural Resources",
        "summary_lines": [
            "The bill updates reclamation plans and bonds.",
            "The bill coordinates mining and oil and gas conservation standards.",
            "The bill creates penalties for knowing violations.",
        ],
        "sections": [
            {
                "number": 1,
                "lead": f"{SECTION_SYMBOL} 34-32-116, C.R.S., is amended to read:",
                "body": [
                    "(1) An operator shall file a reclamation plan before disturbing affected land.",
                    "(2) As used in this section:",
                    "(a) 'affected land' means land from which overburden or minerals are removed, land on which development waste is placed, and land affected by mining operations.",
                    "(3) The Senate Agriculture & Natural Resources Committee shall receive a report on reclamation bond adequacy by September 1, 2025.",
                    "(4) A reclamation bond must be sufficient to complete reclamation if the operator defaults.",
                    "(5) The board may require additional financial assurance after an inspection.",
                    "(6) The board shall consider water quality impacts and revegetation requirements.",
                ],
            },
            {
                "number": 2,
                "lead": f"{SECTION_SYMBOL} 34-60-106, C.R.S., is amended to read:",
                "body": [
                    "(1) The commission may coordinate oil and gas conservation standards with mined land reclamation requirements.",
                    "(2) A person who knowingly violates a reclamation bond order commits a class 2 misdemeanor and may be fined $15,000.",
                    "(3) The commission may share inspection data with the mined land reclamation board.",
                    "(4) A corrective action order must state the factual basis for the violation.",
                ],
            },
            {
                "number": 3,
                "heading": "Effective date.",
                "body": ["This act takes effect September 1, 2025."],
            },
        ],
    },
    {
        "bill_number": "HB25-1099",
        "title": "CONCERNING MODIFICATIONS TO THE STATE INCOME TAX CREDIT FOR CAPITAL INVESTMENT",
        "house_sponsors": ["Nguyen", "Davis", "Clark"],
        "senate_sponsors": ["Robinson", "Taylor"],
        "committee": "Finance",
        "domain": "Taxation / Finance",
        "summary_lines": [
            "The bill modifies a state income tax credit.",
            "The bill caps annual program certification amounts.",
            "The bill requires rulemaking under the Administrative Procedure Act.",
        ],
        "sections": [
            {
                "number": 1,
                "lead": f"{SECTION_SYMBOL} 39-22-104, C.R.S., is amended to read:",
                "body": [
                    "(1) A taxpayer may claim a credit for a qualified capital investment placed in service during an income tax year.",
                    "(2) As used in this section:",
                    "(a) 'qualified capital investment' means an investment in machinery, equipment, technology infrastructure, or industrial property used in Colorado.",
                    "(3) The credit is capped at $10,000 for each qualified taxpayer.",
                    "(4) The department of revenue shall publish application forms by January 1, 2026.",
                    "(5) A taxpayer shall retain documentation for at least four tax years.",
                ],
            },
            {
                "number": 2,
                "lead": f"{SECTION_SYMBOL} 39-22-514, C.R.S., is amended to read:",
                "body": [
                    "(1) The aggregate amount of credits certified in a state fiscal year shall not exceed $50,000,000.",
                    "(2) The House Finance Committee shall review annual program performance data.",
                    "(3) The department may prorate credits if applications exceed the annual program cap.",
                    "(4) The department shall publish the amount of unused credit authority each year.",
                ],
            },
            {
                "number": 3,
                "lead": f"{SECTION_SYMBOL} 24-4-103, C.R.S., is amended to read:",
                "body": [
                    "(1) The department of revenue shall promulgate rules for the capital investment credit in accordance with the state administrative procedure act.",
                    "(2) The rules must establish application deadlines, required documentation, and audit procedures.",
                    "(3) For administration, $250,000 is appropriated from the General Fund to the department of revenue.",
                    "(4) The department may consult with the office of economic development.",
                ],
            },
            {
                "number": 4,
                "heading": "Effective date.",
                "body": ["This act applies to tax years starting on or after January 1, 2026."],
            },
        ],
    },
]


def generate_bill_text(bill_config: dict) -> str:
    """Generate realistic Colorado bill text from a bill configuration.

    Args:
        bill_config: One entry from ``SAMPLE_BILLS``.

    Returns:
        Full line-numbered bill text in a Colorado legislative style.
    """
    lines = build_unnumbered_bill_lines(bill_config)
    lines = ensure_realistic_length(lines, bill_config)
    return add_line_numbers(lines)


def generate_extracted_json(bill_text: str, bill_number: str) -> dict[str, Any]:
    """Wrap generated bill text in extractor-compatible JSON.

    Args:
        bill_text: Full generated bill text.
        bill_number: Canonical bill number such as ``HB25-1001``.

    Returns:
        Extraction JSON shaped like ``extractor.py`` output.
    """
    page_texts = split_pages(bill_text, lines_per_page=LINES_PER_PAGE)
    pages = [
        {
            "page_number": index,
            "text": page_text,
            "char_count": len(page_text),
        }
        for index, page_text in enumerate(page_texts, start=1)
    ]
    full_text = PAGE_BREAK.join(page_texts)
    return {
        "source_file": f"{bill_number}.pdf",
        "extractor": "sample_generator",
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
        "total_chars": len(full_text),
    }


def generate_all_samples(
    output_dir: str = DEFAULT_SAMPLE_DIR,
    count: int = 5,
) -> dict[str, Any]:
    """Generate sample extracted JSON files.

    Args:
        output_dir: Directory where sample extracted JSON files are written.
        count: Number of hardcoded bills to generate, capped at available bills.

    Returns:
        Summary with generated count, output directory, and bill numbers.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    selected_bills = SAMPLE_BILLS[: max(0, min(count, len(SAMPLE_BILLS)))]
    bill_numbers: list[str] = []

    for bill_config in selected_bills:
        bill_number = str(bill_config["bill_number"])
        bill_text = generate_bill_text(bill_config)
        payload = generate_extracted_json(bill_text, bill_number)
        write_json(output_path / f"{bill_number}_extracted.json", payload)
        bill_numbers.append(bill_number)

    return {
        "generated": len(bill_numbers),
        "output_dir": str(output_path),
        "bills": bill_numbers,
    }


def seed_pipeline(
    sample_dir: str = DEFAULT_SAMPLE_DIR,
    target_dir: str = DEFAULT_PIPELINE_SEED_DIR,
) -> dict[str, int]:
    """Copy generated samples into the parser input directory.

    Args:
        sample_dir: Directory containing sample ``*_extracted.json`` files.
        target_dir: Directory used by the parser stage.

    Returns:
        Copy summary with copied and skipped counts.
    """
    sample_path = Path(sample_dir)
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0

    for source in sorted(sample_path.glob("*_extracted.json")):
        destination = target_path / source.name
        if destination.exists():
            skipped += 1
            continue
        shutil.copy2(source, destination)
        copied += 1

    return {"copied": copied, "skipped": skipped}


def generate_sample_data(
    output_dir: str = DEFAULT_PIPELINE_SEED_DIR,
    sample_dir: str = DEFAULT_SAMPLE_DIR,
) -> dict[str, Any]:
    """Generate samples and seed the pipeline for backward compatibility.

    Args:
        output_dir: Parser input directory to seed.
        sample_dir: Sample corpus directory.

    Returns:
        Combined generation and seed summary.
    """
    generated = generate_all_samples(sample_dir, count=len(SAMPLE_BILLS))
    seeded = seed_pipeline(sample_dir, output_dir)
    return {
        "generated": generated["generated"],
        "sample_dir": generated["output_dir"],
        "output_dir": output_dir,
        "bills": generated["bills"],
        "copied": seeded["copied"],
        "skipped": seeded["skipped"],
    }


def build_unnumbered_bill_lines(bill_config: dict[str, Any]) -> list[str]:
    """Build unnumbered bill lines before margin numbers are applied.

    Args:
        bill_config: One entry from ``SAMPLE_BILLS``.

    Returns:
        Unnumbered bill text lines.
    """
    house_sponsors = ", ".join(bill_config["house_sponsors"])
    senate_sponsors = ", ".join(bill_config["senate_sponsors"])
    lines = [
        str(bill_config["bill_number"]),
        "A BILL FOR AN ACT",
        str(bill_config["title"]) + ".",
        "",
        f"BY REPRESENTATIVE(S) {house_sponsors}",
        f"BY SENATOR(S) {senate_sponsors}",
        "",
        f"Committee on {bill_config['committee']}",
        "",
        "Bill Summary",
    ]
    lines.extend(str(line) for line in bill_config["summary_lines"])
    lines.extend(
        [
            "",
            "Legislative declaration.",
            "(1) The general assembly finds that Colorado law should be clear,",
            "predictable, and capable of deterministic analysis by public users.",
            "(2) The general assembly further finds that the subject matter of",
            "this act requires coordinated implementation by state agencies.",
            "",
            "BE IT ENACTED BY THE GENERAL ASSEMBLY OF THE STATE OF COLORADO:",
            "",
        ]
    )

    for section in bill_config["sections"]:
        lines.extend(section_to_lines(section))
        lines.append("")

    return lines


def section_to_lines(section: dict[str, Any]) -> list[str]:
    """Convert one section config to bill text lines.

    Args:
        section: Section configuration dictionary.

    Returns:
        Legal text lines for the section.
    """
    number = section["number"]
    heading = section.get("heading")
    if heading:
        lines = [f"SECTION {number}. {heading}"]
    else:
        lines = [f"SECTION {number}.", str(section["lead"])]
    lines.extend(str(line) for line in section["body"])
    return lines


def ensure_realistic_length(lines: list[str], bill_config: dict[str, Any]) -> list[str]:
    """Pad bill text to a realistic 60-120 line range.

    Args:
        lines: Initial bill lines.
        bill_config: Bill configuration used to tailor filler lines.

    Returns:
        Bill lines with deterministic procedural language added if needed.
    """
    target_min = 65
    if len(lines) >= target_min:
        return lines[:120]

    insertion_index = max(0, len(lines) - 2)
    domain = str(bill_config.get("domain", "legislative implementation"))
    committee = str(bill_config.get("committee", "the committee of reference"))
    filler = [
        f"The administering agency shall consult with stakeholders in the {domain} field.",
        f"The administering agency shall present implementation updates to the {committee} Committee.",
        "Rules adopted under this act must be posted on the agency website.",
        "The agency may use electronic forms to receive applications and reports.",
        "A regulated person may request technical assistance before a deadline.",
        "Nothing in this act limits authority granted under any other state law.",
        "The agency shall maintain records sufficient for audit and public review.",
        "The agency shall coordinate with local governments when implementation affects local permits.",
    ]

    padded = list(lines)
    cursor = 0
    while len(padded) < target_min:
        padded.insert(insertion_index, filler[cursor % len(filler)])
        insertion_index += 1
        cursor += 1
    return padded


def add_line_numbers(lines: list[str]) -> str:
    """Prefix non-empty lines with sequential left-margin line numbers.

    Args:
        lines: Unnumbered bill text lines.

    Returns:
        Numbered bill text.
    """
    numbered: list[str] = []
    line_number = 1
    for line in lines:
        if line:
            numbered.append(f"{line_number} {line}")
            line_number += 1
        else:
            numbered.append("")
    return "\n".join(numbered).rstrip() + "\n"


def split_pages(text: str, lines_per_page: int = LINES_PER_PAGE) -> list[str]:
    """Split generated bill text into page-like chunks.

    Args:
        text: Full generated bill text.
        lines_per_page: Approximate line count per generated page.

    Returns:
        Page text chunks.
    """
    lines = text.splitlines()
    pages = [
        "\n".join(lines[index : index + lines_per_page]).strip()
        for index in range(0, len(lines), lines_per_page)
    ]
    return [page for page in pages if page]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with deterministic UTF-8 formatting.

    Args:
        path: Destination file path.
        payload: JSON-serializable payload.
    """
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Generate sample Colorado bill extracted-text JSON files."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_SAMPLE_DIR,
        help=f"Sample output directory. Default: {DEFAULT_SAMPLE_DIR}",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help=f"Copy generated samples to {DEFAULT_PIPELINE_SEED_DIR}.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of sample bills to generate. Default: 5.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sample data generator CLI.

    Args:
        argv: Optional argument sequence for tests.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    summary = generate_all_samples(args.output_dir, args.count)
    print(f"Generated {summary['generated']} sample bills in {summary['output_dir']}")
    if args.seed:
        seed_summary = seed_pipeline(args.output_dir, DEFAULT_PIPELINE_SEED_DIR)
        print(
            "Seeded pipeline: copied "
            f"{seed_summary['copied']} files to {DEFAULT_PIPELINE_SEED_DIR}/"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
