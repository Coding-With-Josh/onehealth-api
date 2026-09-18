from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.utils import timezone


def seed_database():
    """
    Seed the database with realistic development/test data.

    Run from Django shell:

        from seed_data import seed_database
        seed_database()
    """

    def get_model(model_name):
        """
        Find a model by class name regardless of which Django app contains it.
        """
        for model in apps.get_models():
            if model.__name__ == model_name:
                return model

        raise LookupError(
            f"Could not find model '{model_name}'. "
            f"Make sure the app containing it is installed."
        )

    # ------------------------------------------------------------------
    # MODELS
    # ------------------------------------------------------------------

    User = get_model("User")
    Hospital = get_model("Hospital")
    PatientProfile = get_model("PatientProfile")
    HospitalStaffProfile = get_model("HospitalStaffProfile")

    Visit = get_model("Visit")
    Vital = get_model("Vital")
    Medication = get_model("Medication")

    EmergencyContact = get_model("EmergencyContact")
    AccessRequest = get_model("AccessRequest")
    AccessGrant = get_model("AccessGrant")
    EmergencyEscalation = get_model("EmergencyEscalation")

    AuditLog = get_model("AuditLog")
    PatientCard = get_model("PatientCard")
    MedicalRecord = get_model("MedicalRecord")

    # ------------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------------

    def create_user(email, phone, user_type, password="TestPassword123!"):
        """
        Create a user without depending on the exact implementation
        of the custom UserManager.
        """

        user = User.objects.filter(email=email).first()

        if user:
            return user

        user = User(
            email=email,
            phone_number=phone,
            user_type=user_type,
            is_active=True,
        )

        user.set_password(password)
        user.save()

        return user

    with transaction.atomic():

        # ==============================================================
        # 1. HOSPITALS
        # ==============================================================

        hospitals_data = [
            {
                "name": "DeltaCare General Hospital",
                "registration_number": "NHFR-DEL-00001",
                "phermc_number": "PHERMC-DEL-00001",
                "cac_number": "CAC-DEL-100001",
                "address": "12 Airport Road, Warri, Delta State",
                "latitude": Decimal("5.516700"),
                "longitude": Decimal("5.750000"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
            {
                "name": "RiverView Specialist Hospital",
                "registration_number": "NHFR-RIV-00002",
                "phermc_number": "PHERMC-RIV-00002",
                "cac_number": "CAC-RIV-100002",
                "address": "24 Aba Road, Port Harcourt, Rivers State",
                "latitude": Decimal("4.815600"),
                "longitude": Decimal("7.049800"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
            {
                "name": "Lagos Metropolitan Hospital",
                "registration_number": "NHFR-LAG-00003",
                "phermc_number": "PHERMC-LAG-00003",
                "cac_number": "CAC-LAG-100003",
                "address": "18 Admiralty Way, Lekki, Lagos State",
                "latitude": Decimal("6.447400"),
                "longitude": Decimal("3.472200"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
            {
                "name": "Abuja Prime Medical Centre",
                "registration_number": "NHFR-FCT-00004",
                "phermc_number": "PHERMC-FCT-00004",
                "cac_number": "CAC-FCT-100004",
                "address": "15 Aminu Kano Crescent, Wuse 2, Abuja",
                "latitude": Decimal("9.076500"),
                "longitude": Decimal("7.398600"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
            {
                "name": "Edo Wellness Hospital",
                "registration_number": "NHFR-EDO-00005",
                "phermc_number": "PHERMC-EDO-00005",
                "cac_number": "CAC-EDO-100005",
                "address": "7 Sapele Road, Benin City, Edo State",
                "latitude": Decimal("6.335000"),
                "longitude": Decimal("5.603700"),
                "status": Hospital.VerificationStatus.PENDING,
            },
            {
                "name": "Sunrise Community Hospital",
                "registration_number": "NHFR-OYO-00006",
                "phermc_number": "PHERMC-OYO-000006",
                "cac_number": "CAC-OYO-100006",
                "address": "31 Ring Road, Ibadan, Oyo State",
                "latitude": Decimal("7.377500"),
                "longitude": Decimal("3.947000"),
                "status": Hospital.VerificationStatus.PENDING,
            },
            {
                "name": "Northern Crescent Hospital",
                "registration_number": "NHFR-KAD-00007",
                "phermc_number": "PHERMC-KAD-100007",
                "cac_number": "CAC-KAD-100007",
                "address": "22 Independence Way, Kaduna, Kaduna State",
                "latitude": Decimal("10.510500"),
                "longitude": Decimal("7.416500"),
                "status": Hospital.VerificationStatus.REJECTED,
            },
            {
                "name": "Lifeline Specialist Clinic",
                "registration_number": "NHFR-ENU-00008",
                "phermc_number": "PHERMC-ENU-100008",
                "cac_number": "CAC-ENU-100008",
                "address": "9 Ogui Road, Enugu, Enugu State",
                "latitude": Decimal("6.458400"),
                "longitude": Decimal("7.546400"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
            {
                "name": "Greenfield Medical Hospital",
                "registration_number": "NHFR-KW-00009",
                "phermc_number": "PHERMC-KW-100009",
                "cac_number": "CAC-KW-100009",
                "address": "14 Fate Road, Ilorin, Kwara State",
                "latitude": Decimal("8.496600"),
                "longitude": Decimal("4.542600"),
                "status": Hospital.VerificationStatus.SUSPENDED,
            },
            {
                "name": "Coastal Hope Hospital",
                "registration_number": "NHFR-AK-00010",
                "phermc_number": "PHERMC-AK-100010",
                "cac_number": "CAC-AK-100010",
                "address": "5 Udo Udoma Avenue, Uyo, Akwa Ibom State",
                "latitude": Decimal("5.037700"),
                "longitude": Decimal("7.912800"),
                "status": Hospital.VerificationStatus.VERIFIED,
            },
        ]

        hospitals = []

        for data in hospitals_data:
            hospital, created = Hospital.objects.get_or_create(
                registration_number=data["registration_number"],
                defaults={
                    "name": data["name"],
                    "phermc_number": data["phermc_number"],
                    "cac_number": data["cac_number"],
                    "address": data["address"],
                    "latitude": data["latitude"],
                    "longitude": data["longitude"],
                    "verification_status": data["status"],
                    "verified_at": (
                        timezone.now()
                        if data["status"] == Hospital.VerificationStatus.VERIFIED
                        else None
                    ),
                },
            )

            hospitals.append(hospital)

        print(f"✓ Hospitals: {len(hospitals)}")

        # ==============================================================
        # 2. PATIENT USERS
        # ==============================================================

        patients_data = [
            ("Chinedu Okafor", "chinedu.okafor@example.com", "08030000001"),
            ("Amaka Eze", "amaka.eze@example.com", "08030000002"),
            ("David Johnson", "david.johnson@example.com", "08030000003"),
            ("Blessing Williams", "blessing.williams@example.com", "08030000004"),
            ("Ibrahim Musa", "ibrahim.musa@example.com", "08030000005"),
            ("Grace Adeyemi", "grace.adeyemi@example.com", "08030000006"),
            ("Daniel Osei", "daniel.osei@example.com", "08030000007"),
            ("Mary Joseph", "mary.joseph@example.com", "08030000008"),
            ("Emeka Nwosu", "emeka.nwosu@example.com", "08030000009"),
            ("Sarah Ibrahim", "sarah.ibrahim@example.com", "08030000010"),
        ]

        patient_users = []

        for index, (name, email, phone) in enumerate(patients_data, start=1):
            user = create_user(
                email=email,
                phone=phone,
                user_type=User.UserType.PATIENT,
            )

            patient_users.append(user)

        print(f"✓ Patient users: {len(patient_users)}")

        # ==============================================================
        # 3. HOSPITAL STAFF USERS
        # ==============================================================

        staff_data = [
            ("Dr. Adebayo Adekunle", "adebayo.doctor@deltacare.test", "08110000001", 0, "doctor"),
            ("Nurse Mercy James", "mercy.nurse@deltacare.test", "08110000002", 0, "nurse"),
            ("Peter Okoro", "peter.admin@deltacare.test", "08110000003", 0, "admin"),

            ("Dr. Chika Nnamdi", "chika.doctor@riverview.test", "08110000004", 1, "doctor"),
            ("Nurse Esther Paul", "esther.nurse@riverview.test", "08110000005", 1, "nurse"),

            ("Dr. Tunde Balogun", "tunde.doctor@lagosmetro.test", "08110000006", 2, "doctor"),
            ("Mrs. Ada Obi", "ada.admin@lagosmetro.test", "08110000007", 2, "admin"),

            ("Dr. Yusuf Bello", "yusuf.doctor@abujaprime.test", "08110000008", 3, "doctor"),
            ("Nurse Fatima Ahmed", "fatima.nurse@abujaprime.test", "08110000009", 3, "nurse"),

            ("Dr. Emeka Obi", "emeka.doctor@lifeline.test", "08110000010", 7, "doctor"),
            ("Nurse Janet Okeke", "janet.nurse@lifeline.test", "08110000011", 7, "nurse"),
        ]

        staff_profiles = []

        for name, email, phone, hospital_index, role in staff_data:

            user = create_user(
                email=email,
                phone=phone,
                user_type=User.UserType.HOSPITAL_STAFF,
            )

            hospital = hospitals[hospital_index]

            staff, created = HospitalStaffProfile.objects.get_or_create(
                user=user,
                defaults={
                    "hospital": hospital,
                    "full_name": name,
                    "role": role,
                    "professional_license_number": (
                        f"MDCN-TEST-{hospital_index + 1:02d}{len(staff_profiles) + 1:04d}"
                        if role == "doctor"
                        else ""
                    ),
                },
            )

            staff_profiles.append(staff)

        print(f"✓ Hospital staff: {len(staff_profiles)}")

        # ==============================================================
        # 4. PATIENT PROFILES
        # ==============================================================

        patient_profile_data = [
            ("Chinedu Okafor", "1992-05-14", "Male", "O+", "self_managed"),
            ("Amaka Eze", "1988-11-22", "Female", "A+", "self_managed"),
            ("David Johnson", "1979-02-10", "Male", "B+", "self_managed"),
            ("Blessing Williams", "1995-08-03", "Female", "O-", "self_managed"),
            ("Ibrahim Musa", "1968-04-19", "Male", "AB+", "self_managed"),
            ("Grace Adeyemi", "2001-12-07", "Female", "A-", "self_managed"),
            ("Daniel Osei", "1985-06-28", "Male", "B-", "self_managed"),
            ("Mary Joseph", "1990-09-15", "Female", "O+", "self_managed"),
            ("Emeka Nwosu", "1974-03-11", "Male", "A+", "self_managed"),
            ("Sarah Ibrahim", "1998-01-30", "Female", "B+", "self_managed"),
        ]

        patients = []

        for index, (name, dob, gender, blood_type, account_type) in enumerate(
            patient_profile_data
        ):
            profile, created = PatientProfile.objects.get_or_create(
                user=patient_users[index],
                defaults={
                    "full_name": name,
                    "date_of_birth": dob,
                    "gender": gender,
                    "blood_type": blood_type,
                    "account_type": account_type,
                },
            )

            patients.append(profile)

        print(f"✓ Patient profiles: {len(patients)}")

        # ==============================================================
        # 5. DEPENDENT PATIENT
        # ==============================================================

        dependent = PatientProfile.objects.filter(
            full_name="Baby Chinedu Okafor"
        ).first()

        if not dependent:
            dependent = PatientProfile.objects.create(
                full_name="Baby Chinedu Okafor",
                date_of_birth="2024-09-18",
                gender="Male",
                blood_type="O+",
                account_type=PatientProfile.AccountType.DEPENDENT,
                guardian=patients[0],
            )

        patients.append(dependent)

        print("✓ Dependent patient created")

        # ==============================================================
        # 6. COMMUNITY-ENROLLED PATIENT
        # ==============================================================

        community_patient = PatientProfile.objects.filter(
            full_name="Musa Abdullahi"
        ).first()

        if not community_patient:
            community_patient = PatientProfile.objects.create(
                full_name="Musa Abdullahi",
                date_of_birth="1959-07-21",
                gender="Male",
                blood_type="A+",
                account_type=PatientProfile.AccountType.COMMUNITY_ENROLLED,
                enrolled_by_staff=staff_profiles[0],
            )

        patients.append(community_patient)

        print("✓ Community-enrolled patient created")

        # ==============================================================
        # 7. EMERGENCY CONTACTS
        # ==============================================================

        emergency_contacts_data = [
            (patients[0], "Ngozi Okafor", "Wife", "08040000001", "ngozi.okafor@example.com"),
            (patients[0], "Emeka Okafor", "Brother", "08040000002", "emeka.okafor@example.com"),

            (patients[1], "Chidi Eze", "Husband", "08040000003", "chidi.eze@example.com"),

            (patients[2], "Michael Johnson", "Brother", "08040000004", "michael.johnson@example.com"),

            (patients[3], "Helen Williams", "Mother", "08040000005", "helen.williams@example.com"),

            (patients[4], "Aisha Musa", "Wife", "08040000006", "aisha.musa@example.com"),

            (patients[5], "Samuel Adeyemi", "Father", "08040000007", "samuel.adeyemi@example.com"),

            (patients[6], "Linda Osei", "Wife", "08040000008", "linda.osei@example.com"),

            (patients[7], "Joseph Joseph", "Brother", "08040000009", "joseph.joseph@example.com"),

            (patients[8], "Ada Nwosu", "Wife", "08040000010", "ada.nwosu@example.com"),

            (patients[9], "Fatima Ibrahim", "Sister", "08040000011", "fatima.ibrahim@example.com"),
        ]

        contacts = []

        for patient, name, relationship, phone, email in emergency_contacts_data:

            contact, created = EmergencyContact.objects.get_or_create(
                patient=patient,
                phone_number=phone,
                defaults={
                    "full_name": name,
                    "relationship": relationship,
                    "email": email,
                    "priority_order": 1,
                    "is_active": True,
                },
            )

            contacts.append(contact)

        print(f"✓ Emergency contacts: {len(contacts)}")

        # ==============================================================
        # 8. VISITS
        # ==============================================================

        visits = []

        visit_data = [
            (0, 0, 0, "active"),
            (1, 0, 1, "active"),
            (2, 1, 3, "active"),
            (3, 1, 3, "checked_out"),
            (4, 2, 5, "active"),
            (5, 2, 5, "checked_out"),
            (6, 3, 7, "active"),
            (7, 3, 7, "checked_out"),
            (8, 7, 9, "active"),
            (9, 7, 9, "checked_out"),
            (0, 1, 3, "checked_out"),
            (2, 0, 0, "checked_out"),
            (4, 3, 7, "active"),
            (8, 2, 5, "active"),
        ]

        for index, (patient_index, hospital_index, staff_index, status) in enumerate(
            visit_data,
            start=1,
        ):
            patient = patients[patient_index]
            hospital = hospitals[hospital_index]
            staff = staff_profiles[staff_index]

            existing = Visit.objects.filter(
                patient=patient,
                hospital=hospital,
            ).first()

            if existing:
                visits.append(existing)
                continue

            admitted_at = timezone.now() - timedelta(days=index)

            visit = Visit(
                patient=patient,
                hospital=hospital,
                admitted_at=admitted_at,
                status=status,
                created_by_staff=staff,
            )

            if status == Visit.Status.CHECKED_OUT:
                visit.checked_out_at = admitted_at + timedelta(hours=5)

            visit.save()
            visits.append(visit)

        print(f"✓ Visits: {len(visits)}")

        # ==============================================================
        # 9. VITALS
        # ==============================================================
        # Only active visits can receive vitals.

        vital_values = [
            (120, 80, 72, "36.7", 16, "98.0", "72.50", "178.00", "Patient stable."),
            (118, 76, 68, "36.5", 15, "99.0", "64.20", "165.00", "No immediate concerns."),
            (135, 88, 84, "37.2", 18, "97.0", "82.40", "180.00", "Mildly elevated blood pressure."),
            (110, 70, 75, "36.8", 16, "99.0", "58.30", "160.00", "Vitals within normal range."),
            (142, 92, 91, "37.4", 20, "96.0", "91.00", "175.00", "Patient reports headache."),
            (125, 82, 79, "36.6", 17, "98.0", "70.10", "172.00", "Stable."),
            (130, 85, 88, "37.0", 18, "97.0", "76.50", "169.00", "Routine assessment."),
            (116, 74, 70, "36.4", 15, "99.0", "62.00", "163.00", "Stable."),
        ]

        vitals = []

        active_visits = [
            visit for visit in visits
            if visit.status == Visit.Status.ACTIVE
        ]

        for index, visit in enumerate(active_visits):

            values = vital_values[index % len(vital_values)]

            existing = Vital.objects.filter(visit=visit).first()

            if existing:
                vitals.append(existing)
                continue

            vital = Vital.objects.create(
                visit=visit,
                recorded_by_staff=visit.created_by_staff,
                blood_pressure_systolic=values[0],
                blood_pressure_diastolic=values[1],
                heart_rate=values[2],
                temperature_c=Decimal(values[3]),
                respiratory_rate=values[4],
                oxygen_saturation=Decimal(values[5]),
                weight_kg=Decimal(values[6]),
                height_cm=Decimal(values[7]),
                notes=values[8],
            )

            vitals.append(vital)

        print(f"✓ Vitals: {len(vitals)}")

        # ==============================================================
        # 10. PATIENT CARDS
        # ==============================================================

        cards = []

        for index, patient in enumerate(patients[:10]):

            existing = PatientCard.objects.filter(
                patient=patient,
                status=PatientCard.Status.ACTIVE,
            ).first()

            if existing:
                cards.append(existing)
                continue

            card = PatientCard.objects.create(
                patient=patient,
                expires_at=timezone.now() + timedelta(days=365),
                status=PatientCard.Status.ACTIVE,
            )

            cards.append(card)

        print(f"✓ Patient cards: {len(cards)}")

        # ==============================================================
        # 11. MEDICAL RECORDS
        # ==============================================================

        medical_records_data = [
            (0, "Allergy", "Patient reports allergy to penicillin.", False),
            (0, "Diagnosis", "History of mild asthma.", True),
            (1, "Diagnosis", "Hypertension under monitoring.", True),
            (2, "Diagnosis", "Type 2 diabetes mellitus.", True),
            (3, "Medical History", "Previous appendectomy in 2019.", True),
            (4, "Diagnosis", "Elevated blood pressure noted during visit.", True),
            (5, "Allergy", "No known drug allergies reported.", False),
            (6, "Diagnosis", "Seasonal allergic rhinitis.", True),
            (7, "Medical History", "Previous treatment for malaria.", True),
            (8, "Diagnosis", "Hyperlipidemia under monitoring.", True),
            (9, "Medical History", "No significant previous surgical history.", False),
        ]

        medical_records = []

        for index, (patient_index, entry_type, description, verified) in enumerate(
            medical_records_data
        ):

            patient = patients[patient_index]

            # Find an active visit for this patient.
            patient_visit = next(
                (
                    visit for visit in visits
                    if visit.patient_id == patient.id
                    and visit.status == Visit.Status.ACTIVE
                ),
                None,
            )

            staff = (
                patient_visit.created_by_staff
                if patient_visit
                else staff_profiles[0]
            )

            if verified and staff.role != HospitalStaffProfile.Role.DOCTOR:
                staff = next(
                    s for s in staff_profiles
                    if s.hospital_id == patient_visit.hospital_id
                    and s.role == HospitalStaffProfile.Role.DOCTOR
                ) if patient_visit else staff_profiles[0]

            existing = MedicalRecord.objects.filter(
                patient=patient,
                entry_type=entry_type,
                description=description,
            ).first()

            if existing:
                medical_records.append(existing)
                continue

            record = MedicalRecord(
                patient=patient,
                entry_type=entry_type,
                description=description,
                verification_status=(
                    MedicalRecord.VerificationStatus.DOCTOR_VERIFIED
                    if verified
                    else MedicalRecord.VerificationStatus.SELF_REPORTED
                ),
                verified_by_staff=staff if verified else None,
                created_by_staff=staff if patient_visit else None,
                visit=patient_visit,
                hospital=patient_visit.hospital if patient_visit else None,
            )

            record.save()
            medical_records.append(record)

        print(f"✓ Medical records: {len(medical_records)}")

        # ==============================================================
        # 12. MEDICATIONS
        # ==============================================================

        medications_data = [
            (0, "Salbutamol Inhaler", "100 mcg", "Inhalation", "As needed", "30 days", "Asthma management", "current"),
            (1, "Amlodipine", "5 mg", "Oral", "Once daily", "90 days", "Blood pressure control", "current"),
            (2, "Metformin", "500 mg", "Oral", "Twice daily", "90 days", "Diabetes management", "current"),
            (3, "Paracetamol", "500 mg", "Oral", "Every 6 hours as needed", "5 days", "Pain relief", "previous"),
            (4, "Losartan", "50 mg", "Oral", "Once daily", "60 days", "Hypertension", "current"),
            (5, "Cetirizine", "10 mg", "Oral", "Once daily", "14 days", "Allergy symptoms", "previous"),
            (6, "Atorvastatin", "20 mg", "Oral", "Once nightly", "90 days", "Cholesterol management", "current"),
            (7, "Artemether/Lumefantrine", "20/120 mg", "Oral", "Twice daily", "3 days", "Malaria treatment", "previous"),
            (8, "Omeprazole", "20 mg", "Oral", "Once daily", "30 days", "Gastric symptoms", "current"),
            (9, "Ibuprofen", "400 mg", "Oral", "Every 8 hours as needed", "5 days", "Pain and inflammation", "previous"),
        ]

        medications = []

        for patient_index, medication_name, dose, route, frequency, duration, reason, status in medications_data:

            patient = patients[patient_index]

            patient_visit = next(
                (
                    visit for visit in visits
                    if visit.patient_id == patient.id
                    and visit.status == Visit.Status.ACTIVE
                ),
                None,
            )

            staff = patient_visit.created_by_staff if patient_visit else staff_profiles[0]

            existing = Medication.objects.filter(
                patient=patient,
                medication=medication_name,
            ).first()

            if existing:
                medications.append(existing)
                continue

            medication = Medication.objects.create(
                patient=patient,
                visit=patient_visit,
                medication=medication_name,
                dose=dose,
                route=route,
                frequency=frequency,
                duration=duration,
                reason=reason,
                status=status,
                prescribed_by_staff=staff,
            )

            medications.append(medication)

        print(f"✓ Medications: {len(medications)}")

        # ==============================================================
        # 13. ACCESS REQUESTS
        # ==============================================================

        access_requests = []

        # Patient 0 at DeltaCare, requested by DeltaCare doctor
        access_request_data = [
            {
                "patient": patients[0],
                "hospital": hospitals[0],
                "staff": staff_profiles[0],
                "request_type": AccessRequest.RequestType.NORMAL,
                "access_level": AccessRequest.AccessLevel.FULL_RECORD,
                "status": AccessRequest.Status.APPROVED,
            },
            {
                "patient": patients[1],
                "hospital": hospitals[0],
                "staff": staff_profiles[1],
                "request_type": AccessRequest.RequestType.EMERGENCY,
                "access_level": AccessRequest.AccessLevel.CRITICAL_INFO_ONLY,
                "status": AccessRequest.Status.PENDING,
            },
            {
                "patient": patients[2],
                "hospital": hospitals[1],
                "staff": staff_profiles[3],
                "request_type": AccessRequest.RequestType.NORMAL,
                "access_level": AccessRequest.AccessLevel.FULL_RECORD,
                "status": AccessRequest.Status.APPROVED,
            },
            {
                "patient": patients[4],
                "hospital": hospitals[2],
                "staff": staff_profiles[5],
                "request_type": AccessRequest.RequestType.NORMAL,
                "access_level": AccessRequest.AccessLevel.CRITICAL_INFO_ONLY,
                "status": AccessRequest.Status.DENIED,
            },
            {
                "patient": patients[6],
                "hospital": hospitals[3],
                "staff": staff_profiles[7],
                "request_type": AccessRequest.RequestType.EMERGENCY,
                "access_level": AccessRequest.AccessLevel.FULL_RECORD,
                "status": AccessRequest.Status.APPROVED,
            },
            {
                "patient": patients[8],
                "hospital": hospitals[7],
                "staff": staff_profiles[9],
                "request_type": AccessRequest.RequestType.NORMAL,
                "access_level": AccessRequest.AccessLevel.FULL_RECORD,
                "status": AccessRequest.Status.APPROVED,
            },
        ]

        for data in access_request_data:

            visit = next(
                (
                    v for v in visits
                    if v.patient_id == data["patient"].id
                    and v.hospital_id == data["hospital"].id
                ),
                None,
            )

            if not visit:
                # Create a matching visit if one does not exist.
                visit = Visit.objects.create(
                    patient=data["patient"],
                    hospital=data["hospital"],
                    status=Visit.Status.ACTIVE,
                    created_by_staff=data["staff"],
                )

                visits.append(visit)

            existing = AccessRequest.objects.filter(
                visit=visit,
                patient=data["patient"],
                hospital=data["hospital"],
                requested_by_staff=data["staff"],
            ).first()

            if existing:
                access_requests.append(existing)
                continue

            request = AccessRequest(
                visit=visit,
                patient=data["patient"],
                hospital=data["hospital"],
                requested_by_staff=data["staff"],
                request_type=data["request_type"],
                access_level=data["access_level"],
                status=data["status"],
            )

            request.save()

            if data["status"] != AccessRequest.Status.PENDING:
                request.responded_at = timezone.now()
                request.save(update_fields=["responded_at"])

            access_requests.append(request)

        print(f"✓ Access requests: {len(access_requests)}")

        # ==============================================================
        # 14. ACCESS GRANTS
        # ==============================================================

        grants = []

        approved_requests = [
            request
            for request in access_requests
            if request.status == AccessRequest.Status.APPROVED
            and request.hospital.verification_status
            == Hospital.VerificationStatus.VERIFIED
            and request.visit.status == Visit.Status.ACTIVE
        ]

        for request in approved_requests:

            existing = AccessGrant.objects.filter(
                access_request=request
            ).first()

            if existing:
                grants.append(existing)
                continue

            grant = AccessGrant.objects.create(
                access_request=request,
                access_level=request.access_level,
                granted_at=timezone.now(),
                granted_by=AccessGrant.GrantedBy.PATIENT,
            )

            grants.append(grant)

        print(f"✓ Access grants: {len(grants)}")

        # ==============================================================
        # 15. EMERGENCY ESCALATIONS
        # ==============================================================

        escalations = []

        emergency_requests = [
            request
            for request in access_requests
            if request.request_type == AccessRequest.RequestType.EMERGENCY
        ]

        for request in emergency_requests:

            existing = EmergencyEscalation.objects.filter(
                access_request=request
            ).first()

            if existing:
                escalations.append(existing)
                continue

            escalation = EmergencyEscalation.objects.create(
                access_request=request,
                stage=EmergencyEscalation.Stage.PATIENT_NOTIFIED,
                triggered_at=timezone.now(),
            )

            escalations.append(escalation)

        print(f"✓ Emergency escalations: {len(escalations)}")

        # ==============================================================
        # 16. AUDIT LOGS
        # ==============================================================

        audit_data = [
            (
                patient_users[0],
                hospitals[0],
                patients[0],
                "patient_registered",
                "PatientProfile",
                str(patients[0].id),
                {"source": "seed"},
            ),
            (
                staff_profiles[0].user,
                hospitals[0],
                patients[0],
                "visit_created",
                "Visit",
                str(visits[0].id),
                {"source": "seed"},
            ),
            (
                staff_profiles[0].user,
                hospitals[0],
                patients[0],
                "medical_record_created",
                "MedicalRecord",
                str(medical_records[0].id),
                {"verification": "doctor_verified"},
            ),
            (
                staff_profiles[0].user,
                hospitals[0],
                patients[0],
                "access_requested",
                "AccessRequest",
                str(access_requests[0].id),
                {"access_level": "full_record"},
            ),
            (
                patient_users[0],
                hospitals[0],
                patients[0],
                "access_granted",
                "AccessGrant",
                str(grants[0].id) if grants else "",
                {"granted_by": "patient"},
            ),
            (
                staff_profiles[3].user,
                hospitals[1],
                patients[2],
                "visit_created",
                "Visit",
                str(visits[2].id),
                {"source": "seed"},
            ),
            (
                staff_profiles[5].user,
                hospitals[2],
                patients[4],
                "access_denied",
                "AccessRequest",
                str(access_requests[3].id),
                {"reason": "demo_access_denial"},
            ),
            (
                staff_profiles[7].user,
                hospitals[3],
                patients[6],
                "emergency_access_requested",
                "AccessRequest",
                str(access_requests[4].id),
                {"emergency": True},
            ),
        ]

        audit_logs = []

        for actor, hospital, patient, action, target_type, target_id, metadata in audit_data:

            log = AuditLog.objects.create(
                actor=actor,
                hospital=hospital,
                patient=patient,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata=metadata,
                ip_address="127.0.0.1",
            )

            audit_logs.append(log)

        print(f"✓ Audit logs: {len(audit_logs)}")

        # ==============================================================
        # SUMMARY
        # ==============================================================

        print("\n" + "=" * 60)
        print("DATABASE SEED COMPLETE")
        print("=" * 60)

        print(f"Hospitals:          {Hospital.objects.count()}")
        print(f"Users:              {User.objects.count()}")
        print(f"Patients:           {PatientProfile.objects.count()}")
        print(f"Hospital Staff:     {HospitalStaffProfile.objects.count()}")
        print(f"Visits:             {Visit.objects.count()}")
        print(f"Vitals:             {Vital.objects.count()}")
        print(f"Medical Records:    {MedicalRecord.objects.count()}")
        print(f"Medications:        {Medication.objects.count()}")
        print(f"Patient Cards:      {PatientCard.objects.count()}")
        print(f"Emergency Contacts:{EmergencyContact.objects.count()}")
        print(f"Access Requests:    {AccessRequest.objects.count()}")
        print(f"Access Grants:      {AccessGrant.objects.count()}")
        print(f"Escalations:        {EmergencyEscalation.objects.count()}")
        print(f"Audit Logs:         {AuditLog.objects.count()}")
        print("=" * 60)

        print("\nTest password for seeded login accounts:")
        print("TestPassword123!")

        print("\nSample patient login:")
        print("chinedu.okafor@example.com")

        print("\nSample doctor login:")
        print("adebayo.doctor@deltacare.test")

        print("\nSeed function finished successfully.")

        return {
            "hospitals": Hospital.objects.count(),
            "users": User.objects.count(),
            "patients": PatientProfile.objects.count(),
            "staff": HospitalStaffProfile.objects.count(),
            "visits": Visit.objects.count(),
            "vitals": Vital.objects.count(),
            "medical_records": MedicalRecord.objects.count(),
            "medications": Medication.objects.count(),
            "patient_cards": PatientCard.objects.count(),
            "emergency_contacts": EmergencyContact.objects.count(),
            "access_requests": AccessRequest.objects.count(),
            "access_grants": AccessGrant.objects.count(),
            "escalations": EmergencyEscalation.objects.count(),
            "audit_logs": AuditLog.objects.count(),
        }