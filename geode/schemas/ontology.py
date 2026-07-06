"""Controlled vocabulary from the Project Geode master design."""

from __future__ import annotations

SUBJECT_TAGS = frozenset(
    {
        "environment",
        "air_quality",
        "emissions",
        "water_quality",
        "solid_waste",
        "hazardous_waste",
        "land_use",
        "environmental_cleanup",
        "climate_change",
        "natural_resources",
        "wildlife",
        "water_rights",
        "public_health",
        "communicable_disease",
        "food_safety",
        "drinking_water",
        "radiation_control",
        "health_facilities",
        "emergency_medical",
        "behavioral_health",
        "substance_abuse",
        "vital_records",
        "labor_employment",
        "wages_hours",
        "workplace_safety",
        "workers_compensation",
        "unemployment_insurance",
        "employment_discrimination",
        "child_labor",
        "paid_leave",
        "professional_licensing",
        "medical_licensing",
        "legal_licensing",
        "engineering_licensing",
        "contractor_licensing",
        "real_estate_licensing",
        "financial_licensing",
        "cosmetology",
        "accountancy",
        "business_regulation",
        "corporate_registration",
        "securities",
        "insurance",
        "banking",
        "consumer_protection",
        "trade_practices",
        "cannabis_regulation",
        "alcohol_regulation",
        "gaming",
        "energy",
        "oil_gas",
        "renewable_energy",
        "utility_regulation",
        "pipeline_safety",
        "mining",
        "electric_vehicles",
        "transportation",
        "motor_vehicles",
        "highways",
        "public_transit",
        "vehicle_emissions",
        "commercial_vehicles",
        "education",
        "k12_education",
        "higher_education",
        "charter_schools",
        "school_safety",
        "teacher_licensing",
        "housing",
        "building_codes",
        "affordable_housing",
        "landlord_tenant",
        "short_term_rentals",
        "construction_standards",
        "mobile_homes",
        "homeowner_associations",
        "compliance",
        "permitting",
        "reporting",
        "inspection",
        "enforcement",
        "penalties",
        "disclosure",
        "recordkeeping",
        "government_operations",
        "municipal_authority",
        "state_operations",
        "procurement",
        "elections",
        "open_records",
        "administrative_procedure",
        "rulemaking",
        "sunset_review",
        "technology",
        "data_privacy",
        "cybersecurity",
        "ai_governance",
        "broadband",
        "telecommunications",
        "agriculture",
        "crop_regulation",
        "livestock",
        "pesticides",
        "organic_certification",
        "water_irrigation",
        "criminal_justice",
        "sentencing",
        "corrections",
        "probation",
        "victims_rights",
        "juvenile_justice",
    }
)

INDUSTRY_TAGS = frozenset(
    {
        "agriculture",
        "mining",
        "utilities",
        "construction",
        "manufacturing",
        "wholesale_trade",
        "retail_trade",
        "transportation_warehousing",
        "information",
        "finance_insurance",
        "real_estate",
        "professional_services",
        "management_companies",
        "administrative_support",
        "education_services",
        "healthcare",
        "arts_entertainment",
        "accommodation_food",
        "other_services",
        "public_administration",
        "cannabis",
        "oil_gas",
        "small_business",
    }
)

COMPLIANCE_KEYWORDS = frozenset(
    {
        "permit_required",
        "license_required",
        "registration_required",
        "reporting",
        "disclosure",
        "recordkeeping",
        "inspection",
        "monitoring",
        "fees",
        "penalty",
        "fine",
        "enforcement_action",
        "hearing_required",
        "public_notice",
        "annual_filing",
        "bonding_required",
        "insurance_required",
        "training_required",
        "certification_required",
        "background_check",
    }
)

RULE_TYPES = frozenset(
    {
        "obligation",
        "prohibition",
        "permission",
        "definition",
        "condition",
        "exception",
        "penalty",
        "reporting",
        "standard",
        "procedure",
    }
)

RELATIONSHIP_TYPES = frozenset(
    {
        "authorized_by",
        "implements",
        "amends",
        "creates",
        "repeals",
        "cites",
        "has_rule_citing_statute",
        "supersedes",
        "modified_by",
        "interprets",
        "reviews",
    }
)

EVENT_TYPES = frozenset(
    {
        "bill_signed",
        "bill_introduced",
        "rule_effective",
        "rule_proposed",
        "executive_order",
        "session_law",
        "constitution_amendment",
    }
)

STATUS_VALUES = frozenset(
    {
        "active",
        "repealed",
        "superseded",
        "emergency",
        "expired",
        "rescinded",
        "in_committee",
        "signed",
        "vetoed",
    }
)


def require_known_values(values: list[str], allowed: frozenset[str], label: str) -> list[str]:
    """Validate that every value belongs to a controlled vocabulary."""

    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"unknown {label}: {unknown}")
    return values


def ontology_payload() -> dict[str, object]:
    """Return a JSON-serializable ontology payload."""

    return {
        "schema_version": "1.0",
        "subject_tags": sorted(SUBJECT_TAGS),
        "industry_tags": sorted(INDUSTRY_TAGS),
        "compliance_keywords": sorted(COMPLIANCE_KEYWORDS),
        "enumerations": {
            "rule_type": sorted(RULE_TYPES),
            "relationship_type": sorted(RELATIONSHIP_TYPES),
            "event_type": sorted(EVENT_TYPES),
            "status": sorted(STATUS_VALUES),
        },
    }
