"""
Seeded hospital registry — simulates Nigeria's Health Facility Registry.

In production this data would come from a live API call to
hfr.fmohconnect.gov.ng during hospital registration. For the demo,
we compare the submitted registration_number against this list.
If it matches, the hospital is immediately marked VERIFIED, simulating
the real verification flow without needing the live API.

Each entry represents a real-class Nigerian hospital:
  registration_number — the NHFR ID the hospital admin must enter
  name               — must also match (case-insensitive) to reduce spoofing
"""

KNOWN_HOSPITALS = [
    {
        "name": "Lagos University Teaching Hospital",
        "registration_number": "NHFR-LG-001",
        "address": "Ishaga Road, Surulere, Lagos",
        "phermc_number": "PHERMC-LG-001",
        "cac_number": "CAC-LG-001",
    },
    {
        "name": "University College Hospital Ibadan",
        "registration_number": "NHFR-OY-001",
        "address": "Queen Elizabeth Road, Ibadan, Oyo State",
        "phermc_number": "PHERMC-OY-001",
        "cac_number": "CAC-OY-001",
    },
    {
        "name": "National Hospital Abuja",
        "registration_number": "NHFR-AB-001",
        "address": "Plot 132, Central Business District, Abuja",
        "phermc_number": "PHERMC-AB-001",
        "cac_number": "CAC-AB-001",
    },
    {
        "name": "Aminu Kano Teaching Hospital",
        "registration_number": "NHFR-KN-001",
        "address": "Zaria Road, Kano, Kano State",
        "phermc_number": "PHERMC-KN-001",
        "cac_number": "CAC-KN-001",
    },
    {
        "name": "University of Benin Teaching Hospital",
        "registration_number": "NHFR-ED-001",
        "address": "PMB 1111, Benin City, Edo State",
        "phermc_number": "PHERMC-ED-001",
        "cac_number": "CAC-ED-001",
    },
    {
        "name": "Obafemi Awolowo University Teaching Hospital",
        "registration_number": "NHFR-OS-001",
        "address": "Ile-Ife, Osun State",
        "phermc_number": "PHERMC-OS-001",
        "cac_number": "CAC-OS-001",
    },
    {
        "name": "Jos University Teaching Hospital",
        "registration_number": "NHFR-PL-001",
        "address": "Rantya, Jos, Plateau State",
        "phermc_number": "PHERMC-PL-001",
        "cac_number": "CAC-PL-001",
    },
    {
        "name": "Central Medical Hospital Lagos",
        "registration_number": "NHFR-LG-002",
        "address": "23 Marina Street, Lagos Island, Lagos",
        "phermc_number": "PHERMC-LG-002",
        "cac_number": "CAC-LG-002",
    },
    {
        "name": "St. Nicholas Hospital",
        "registration_number": "NHFR-LG-003",
        "address": "57 Campbell Street, Lagos Island, Lagos",
        "phermc_number": "PHERMC-LG-003",
        "cac_number": "CAC-LG-003",
    },
    {
        "name": "Reddington Hospital",
        "registration_number": "NHFR-LG-004",
        "address": "12 Idowu Martins Street, Victoria Island, Lagos",
        "phermc_number": "PHERMC-LG-004",
        "cac_number": "CAC-LG-004",
    },
]

# Build a fast lookup dict: registration_number → entry
KNOWN_HOSPITALS_BY_REG_NUMBER = {
    h["registration_number"].upper(): h for h in KNOWN_HOSPITALS
}


def verify_against_registry(registration_number: str, hospital_name: str) -> bool:
    """
    Returns True if the submitted registration number exists in our seeded
    registry AND the hospital name matches closely enough (case-insensitive,
    stripped). This simulates what a live NHFR API call would do.
    """
    entry = KNOWN_HOSPITALS_BY_REG_NUMBER.get(registration_number.strip().upper())
    if not entry:
        return False
    return entry["name"].strip().lower() == hospital_name.strip().lower()
