"""
Luma Vaani — Comprehensive Development Seed Script

Creates a fully-wired demo environment:
  - 1 hospital (Luma Demo Hospital)
  - 4 departments (Cardiology, Neurology, Orthopedics, General Medicine)
  - 4 doctors with complete profiles
  - Weekly schedules for each doctor
  - 3 users (SUPER_ADMIN, HOSPITAL_ADMIN, RECEPTIONIST)
  - 2 sample patients
  - 8 knowledge base documents (FAQ, policy, visiting hours, etc.)

Usage (from repo root inside Docker):
    docker compose run --rm api python database/seed/seed_dev.py

Or with make:
    make seed

Credentials printed at end — CHANGE BEFORE ANY REAL DEPLOYMENT.
"""

import asyncio
import sys
import os
from datetime import datetime, time, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "api"))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.modules.hospitals.models import Hospital
from app.modules.auth.models import User
from app.modules.departments.models import Department
from app.modules.doctors.models import Doctor
from app.modules.patients.models import Patient
from app.modules.schedules.models import DoctorSchedule
from app.modules.knowledge.models import KnowledgeDocument


DATABASE_URL = settings.DATABASE_URL


async def seed() -> None:
    print("\n💙 Luma Vaani — Development Seed\n")
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:

        # ── Hospital ───────────────────────────────────────────────────────────
        hospital = Hospital(
            name="Luma Demo Hospital",
            slug="luma-demo",
            contact_email="admin@lumademo.example",
            contact_phone="+91-9999999999",
            address="12 Health Park Road, Koramangala, Bengaluru, Karnataka 560034",
            config={
                "timezone": "Asia/Kolkata",
                "default_language": "en",
                "emergency_phone": "+91-9999999911",
                "emergency_contact": "+91-112",
                "notification_channels": ["SMS", "WHATSAPP", "EMAIL"],
                "working_days": [0, 1, 2, 3, 4, 5],  # Mon–Sat
                "working_hours": {"start": "08:00", "end": "20:00"},
            },
            is_active=True,
        )
        session.add(hospital)
        await session.flush()
        hid = hospital.id
        print(f"  ✅ Hospital:     {hospital.name} [{hid}]")

        # ── Departments ────────────────────────────────────────────────────────
        depts_data = [
            {
                "name": "Cardiology", "slug": "cardiology",
                "description": "Heart and cardiovascular system care",
                "color": "#E53E3E", "icon": "heart",
            },
            {
                "name": "Neurology", "slug": "neurology",
                "description": "Brain, spinal cord, and nervous system",
                "color": "#805AD5", "icon": "brain",
            },
            {
                "name": "Orthopedics", "slug": "orthopedics",
                "description": "Bones, joints, muscles, and spine",
                "color": "#3182CE", "icon": "bone",
            },
            {
                "name": "General Medicine", "slug": "general-medicine",
                "description": "General health check-ups and primary care",
                "color": "#38A169", "icon": "stethoscope",
            },
        ]
        departments = {}
        for d in depts_data:
            dept = Department(hospital_id=hid, **d, is_active=True)
            session.add(dept)
            await session.flush()
            departments[d["slug"]] = dept
            print(f"  ✅ Department:   {dept.name}")

        # ── Doctors ────────────────────────────────────────────────────────────
        doctors_data = [
            {
                "full_name": "Dr. Arjun Sharma", "slug": "arjun-sharma",
                "department": "cardiology",
                "specialization": "Interventional Cardiologist",
                "qualification": "MBBS, MD (Cardiology), DM (Cardiology), AIIMS Delhi",
                "bio": "15 years of experience in interventional cardiology, specialising in angioplasty and stent procedures.",
                "consultation_fee_paise": 150000,  # ₹1500
                "consultation_duration_minutes": 30,
                "languages": ["English", "Hindi", "Kannada"],
                "email": "dr.sharma@lumademo.example",
                "phone": "+91-9811111111",
            },
            {
                "full_name": "Dr. Priya Menon", "slug": "priya-menon",
                "department": "neurology",
                "specialization": "Consultant Neurologist",
                "qualification": "MBBS, MD (Neurology), DM (Neurology), CMC Vellore",
                "bio": "Expert in stroke management, epilepsy, and movement disorders with 12 years of clinical experience.",
                "consultation_fee_paise": 120000,  # ₹1200
                "consultation_duration_minutes": 45,
                "languages": ["English", "Malayalam", "Tamil"],
                "email": "dr.menon@lumademo.example",
                "phone": "+91-9822222222",
            },
            {
                "full_name": "Dr. Suresh Kumar", "slug": "suresh-kumar",
                "department": "orthopedics",
                "specialization": "Joint Replacement Surgeon",
                "qualification": "MBBS, MS (Ortho), Fellowship in Joint Replacement, NIMHANS",
                "bio": "Specialises in minimally invasive knee and hip replacement surgeries. Over 2000 joint replacements performed.",
                "consultation_fee_paise": 100000,  # ₹1000
                "consultation_duration_minutes": 30,
                "languages": ["English", "Hindi", "Telugu"],
                "email": "dr.kumar@lumademo.example",
                "phone": "+91-9833333333",
            },
            {
                "full_name": "Dr. Kavya Reddy", "slug": "kavya-reddy",
                "department": "general-medicine",
                "specialization": "General Physician & Diabetologist",
                "qualification": "MBBS, MD (General Medicine), Bangalore Medical College",
                "bio": "Primary care specialist with expertise in diabetes management, hypertension, and preventive healthcare.",
                "consultation_fee_paise": 60000,   # ₹600
                "consultation_duration_minutes": 20,
                "languages": ["English", "Telugu", "Kannada"],
                "email": "dr.reddy@lumademo.example",
                "phone": "+91-9844444444",
            },
        ]
        doctors = {}
        for d in doctors_data:
            dept_slug = d.pop("department")
            doctor = Doctor(
                hospital_id=hid,
                department_id=departments[dept_slug].id,
                is_active=True,
                is_accepting_patients=True,
                **d,
            )
            session.add(doctor)
            await session.flush()
            doctors[doctor.slug] = doctor
            print(f"  ✅ Doctor:       {doctor.full_name} — {doctor.specialization}")

        # ── Schedules (Mon–Sat for each doctor) ────────────────────────────────
        # day_of_week: 0=Mon … 5=Sat
        schedule_templates = {
            "arjun-sharma":  [(0, "09:00", "13:00"), (2, "09:00", "13:00"), (4, "14:00", "18:00")],
            "priya-menon":   [(1, "10:00", "14:00"), (3, "10:00", "14:00"), (5, "09:00", "13:00")],
            "suresh-kumar":  [(0, "14:00", "18:00"), (2, "14:00", "18:00"), (4, "09:00", "13:00")],
            "kavya-reddy":   [(0, "08:00", "12:00"), (1, "08:00", "12:00"), (2, "08:00", "12:00"),
                              (3, "08:00", "12:00"), (4, "08:00", "12:00"), (5, "08:00", "12:00")],
        }
        for slug, slots in schedule_templates.items():
            for (dow, start, end) in slots:
                sh, sm = map(int, start.split(":"))
                eh, em = map(int, end.split(":"))
                sched = DoctorSchedule(
                    hospital_id=hid,
                    doctor_id=doctors[slug].id,
                    day_of_week=dow,
                    start_time=time(sh, sm),
                    end_time=time(eh, em),
                    slot_duration_minutes=doctors[slug].consultation_duration_minutes,
                    max_slots_override=None,
                    is_active=True,
                )
                session.add(sched)
        await session.flush()
        print(f"  ✅ Schedules:    {sum(len(v) for v in schedule_templates.values())} schedule blocks created")

        # ── Users ──────────────────────────────────────────────────────────────
        users_data = [
            {
                "hospital_id": None,
                "email": "superadmin@lumadev.example",
                "full_name": "Luma Super Admin",
                "phone": None,
                "password": "SuperAdmin@123",
                "role": UserRole.SUPER_ADMIN,
            },
            {
                "hospital_id": hid,
                "email": "admin@lumademo.example",
                "full_name": "Demo Hospital Admin",
                "phone": "+91-9888888888",
                "password": "HospAdmin@123",
                "role": UserRole.HOSPITAL_ADMIN,
            },
            {
                "hospital_id": hid,
                "email": "receptionist@lumademo.example",
                "full_name": "Riya Sharma (Reception)",
                "phone": "+91-9877777777",
                "password": "Reception@123",
                "role": UserRole.RECEPTIONIST,
            },
        ]
        for u in users_data:
            pwd = u.pop("password")
            user = User(
                password_hash=hash_password(pwd),
                is_active=True,
                **u,
            )
            session.add(user)
        await session.flush()
        print(f"  ✅ Users:        {len(users_data)} users created")

        # ── Patients ───────────────────────────────────────────────────────────
        patients_data = [
            {
                "hospital_id": hid,
                "full_name": "Ravi Kumar Joshi",
                "phone": "+91-9000000001",
                "email": "ravi.joshi@example.com",
                "date_of_birth": datetime(1980, 5, 15).date(),
                "gender": "MALE",
                "blood_group": "B+",
                "address": "45 MG Road, Bengaluru 560001",
                "medical_record_number": "LDH-2026-0001",
            },
            {
                "hospital_id": hid,
                "full_name": "Ananya Singh",
                "phone": "+91-9000000002",
                "email": "ananya.singh@example.com",
                "date_of_birth": datetime(1995, 11, 22).date(),
                "gender": "FEMALE",
                "blood_group": "O+",
                "address": "78 Indiranagar, Bengaluru 560038",
                "medical_record_number": "LDH-2026-0002",
            },
        ]
        for p in patients_data:
            patient = Patient(is_active=True, **p)
            session.add(patient)
        await session.flush()
        print(f"  ✅ Patients:     {len(patients_data)} patients created")

        # ── Knowledge Documents ────────────────────────────────────────────────
        knowledge_docs = [
            {
                "title": "Visiting Hours — All Wards",
                "source_type": "VISITING_HOURS",
                "access_scope": "PUBLIC",
                "content": (
                    "General Ward: Monday to Saturday, 10:00 AM to 12:00 PM and 5:00 PM to 7:00 PM.\n"
                    "ICU / ICCU: Only immediate family members. One visitor at a time. 11:00 AM to 12:00 PM and 6:00 PM to 7:00 PM.\n"
                    "Paediatric Ward: Parents may stay 24 hours. Other visitors: 10:00 AM to 12:00 PM.\n"
                    "Maternity Ward: Spouse may remain 24 hours. Other family: 10:00 AM to 8:00 PM.\n"
                    "No visiting on Sundays and public holidays for ICU/ICCU.\n"
                    "Children under 12 are not permitted in ICU."
                ),
                "language": "en",
            },
            {
                "title": "Appointment Cancellation & Rescheduling Policy",
                "source_type": "POLICY",
                "access_scope": "PUBLIC",
                "content": (
                    "Cancellations must be made at least 2 hours before the scheduled appointment.\n"
                    "Late cancellations (within 2 hours) may incur a cancellation fee of ₹200.\n"
                    "No-shows will be charged 50% of the consultation fee.\n"
                    "Rescheduling is free and can be done up to 1 hour before the appointment.\n"
                    "To cancel or reschedule, use the Luma Vaani chat assistant or call our helpline at +91-9999999911.\n"
                    "Refunds for pre-paid consultations are processed within 3–5 working days."
                ),
                "language": "en",
            },
            {
                "title": "Frequently Asked Questions (FAQ)",
                "source_type": "FAQ",
                "access_scope": "PUBLIC",
                "content": (
                    "Q: How do I book an appointment?\n"
                    "A: Chat with Luma Vaani 24/7, or call our helpline. You can also walk in.\n\n"
                    "Q: What documents should I bring?\n"
                    "A: Photo ID, previous medical records, prescriptions, and insurance card if applicable.\n\n"
                    "Q: Is parking available?\n"
                    "A: Yes. Basement parking is available for up to 4 hours free. After that, ₹50 per hour.\n\n"
                    "Q: Do you have a pharmacy?\n"
                    "A: Yes. Our in-house pharmacy is open Monday to Saturday, 8:00 AM to 9:00 PM.\n\n"
                    "Q: Is the hospital cashless for insurance?\n"
                    "A: We support cashless for 50+ insurance providers. Ask our reception to confirm your coverage.\n\n"
                    "Q: Are reports available online?\n"
                    "A: Lab reports are available on the patient portal within 24 hours. Radiology within 48 hours."
                ),
                "language": "en",
            },
            {
                "title": "Contact Numbers & Departments",
                "source_type": "CONTACT_INFO",
                "access_scope": "PUBLIC",
                "content": (
                    "Main Reception: +91-9999999999\n"
                    "Emergency (24/7): +91-9999999911\n"
                    "Cardiology OPD: +91-9999990001\n"
                    "Neurology OPD: +91-9999990002\n"
                    "Orthopedics OPD: +91-9999990003\n"
                    "General Medicine OPD: +91-9999990004\n"
                    "Pharmacy: +91-9999990010\n"
                    "Lab / Diagnostics: +91-9999990011\n"
                    "Billing & Insurance: +91-9999990020\n"
                    "Patient Relations (complaints): +91-9999990030\n"
                    "Email: care@lumademo.example\n"
                    "Address: 12 Health Park Road, Koramangala, Bengaluru 560034"
                ),
                "language": "en",
            },
            {
                "title": "Accepted Insurance & Cashless Partners",
                "source_type": "INSURANCE",
                "access_scope": "PUBLIC",
                "content": (
                    "We support cashless treatment for the following insurers:\n"
                    "- Star Health Insurance\n"
                    "- HDFC ERGO Health\n"
                    "- ICICI Lombard\n"
                    "- Max Bupa (Niva Bupa)\n"
                    "- Bajaj Allianz Health\n"
                    "- New India Assurance\n"
                    "- United India Insurance\n"
                    "- Oriental Insurance\n"
                    "- Religare (Care Health)\n"
                    "- Aditya Birla Health\n"
                    "- Tata AIG Health\n"
                    "- ManipalCigna Health\n\n"
                    "For reimbursement claims, submit original bills and discharge summary to billing.\n"
                    "Corporate TPA: Apollo Munich, Medi Assist, Raksha TPA supported.\n"
                    "ESI / CGHS patients should carry their authorisation letter."
                ),
                "language": "en",
            },
            {
                "title": "Dr. Arjun Sharma — Cardiologist Profile",
                "source_type": "DOCTOR_PROFILE",
                "access_scope": "PUBLIC",
                "content": (
                    "Dr. Arjun Sharma is an Interventional Cardiologist with 15 years of experience.\n"
                    "Qualification: MBBS, MD (Cardiology), DM (Cardiology) — AIIMS Delhi.\n"
                    "Specialisation: Coronary angioplasty, stent implantation, cardiac catheterisation, heart failure management.\n"
                    "OPD Schedule: Monday & Wednesday 9:00 AM–1:00 PM | Friday 2:00 PM–6:00 PM.\n"
                    "Consultation Fee: ₹1500.\n"
                    "Languages: English, Hindi, Kannada.\n"
                    "He is available for second opinions and post-procedure follow-ups."
                ),
                "language": "en",
            },
            {
                "title": "Pre-Appointment Instructions — General",
                "source_type": "PATIENT_INSTRUCTIONS",
                "access_scope": "PUBLIC",
                "content": (
                    "Please arrive 15 minutes before your appointment time for registration.\n"
                    "Carry a valid photo ID (Aadhaar, PAN, Passport, or Driver's licence).\n"
                    "Bring all previous reports, X-rays, scans, and prescription slips.\n"
                    "For blood tests: fast for 8–12 hours unless instructed otherwise.\n"
                    "For imaging (MRI/CT): remove all metal jewellery and inform staff of any implants.\n"
                    "Pregnant women must inform the radiology team before any X-ray or CT scan.\n"
                    "A caretaker may accompany you inside the consultation room.\n"
                    "Payment can be made by cash, card, UPI, or net banking."
                ),
                "language": "en",
            },
            {
                "title": "Hospital Facilities & Amenities",
                "source_type": "GENERAL",
                "access_scope": "PUBLIC",
                "content": (
                    "Luma Demo Hospital offers:\n"
                    "- 200-bed capacity with AC private, semi-private, and general wards\n"
                    "- 24/7 Emergency & Trauma Centre\n"
                    "- Advanced Cardiac Cath Lab\n"
                    "- 3T MRI, 128-slice CT, Digital X-ray, 4D Ultrasound\n"
                    "- NABL-accredited pathology lab\n"
                    "- Modular Operation Theatres (8 OTs)\n"
                    "- ICU, ICCU, NICU, PICU\n"
                    "- In-house pharmacy (8 AM–9 PM)\n"
                    "- Cafeteria (7 AM–10 PM)\n"
                    "- Free Wi-Fi throughout the hospital\n"
                    "- Wheelchair & stretcher service available\n"
                    "- Patient counselling and social work services\n"
                    "- Ambulance service: +91-9999999912"
                ),
                "language": "en",
            },
        ]
        for k in knowledge_docs:
            doc = KnowledgeDocument(
                hospital_id=hid,
                is_active=True,
                embedding_status="PENDING",  # Will be indexed when GEMINI_API_KEY is set
                metadata={},
                **k,
            )
            session.add(doc)
        await session.flush()
        print(f"  ✅ Knowledge:    {len(knowledge_docs)} documents created (status=PENDING — run /reindex to embed)")

        await session.commit()

    await engine.dispose()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("🎉 Seed complete!\n")
    print("  Credentials:")
    print("    SUPER_ADMIN    superadmin@lumadev.example  /  SuperAdmin@123")
    print("    HOSPITAL_ADMIN admin@lumademo.example      /  HospAdmin@123")
    print("    RECEPTIONIST   receptionist@lumademo.example / Reception@123")
    print("\n  API: http://localhost:8000/docs")
    print("  DB:  http://localhost:8080  (Adminer)")
    print("\n  ⚠️  CHANGE ALL CREDENTIALS BEFORE PRODUCTION USE")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
