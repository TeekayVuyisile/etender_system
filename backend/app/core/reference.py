"""Fixed reference data used by company profiles (and later, tender filtering and matching)."""

from typing import Literal, get_args

Province = Literal[
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "Northern Cape",
    "North West",
    "Western Cape",
]

IndustrySector = Literal[
    "Agriculture",
    "Catering and Food Services",
    "Cleaning and Hygiene",
    "Construction and Civil Works",
    "Consulting and Professional Services",
    "Electrical and Mechanical Engineering",
    "Energy and Utilities",
    "Facilities Management",
    "Healthcare and Medical Supplies",
    "IT and Telecommunications",
    "Manufacturing",
    "Office Supplies and Stationery",
    "Security Services",
    "Training and Education",
    "Transport and Logistics",
    "Other",
]

# Main CIDB classes of construction works. Grades run from 1 (smallest contracts) to 9.
CidbClass = Literal["CE", "GB", "EB", "EP", "ME"]

CIDB_CLASS_NAMES: dict[str, str] = {
    "CE": "Civil Engineering",
    "GB": "General Building",
    "EB": "Electrical Engineering (Building)",
    "EP": "Electrical Engineering (Infrastructure)",
    "ME": "Mechanical Engineering",
}

CERTIFICATION_SUGGESTIONS: list[str] = [
    "CSD Registration",
    "SARS Tax Compliance Status",
    "COIDA Letter of Good Standing",
    "ISO 9001",
    "ISO 14001",
    "ISO 45001",
    "PSIRA Registration",
    "SANAS Accreditation",
]

PROVINCES: list[str] = list(get_args(Province))
INDUSTRY_SECTORS: list[str] = list(get_args(IndustrySector))
