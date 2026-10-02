"""
Shared enumerations used across domain models.
"""

import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    HOSPITAL_ADMIN = "HOSPITAL_ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    PATIENT = "PATIENT"


class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class AppointmentType(str, enum.Enum):
    OPD = "OPD"
    FOLLOW_UP = "FOLLOW_UP"
    EMERGENCY = "EMERGENCY"
    CONSULTATION = "CONSULTATION"


class AppointmentSource(str, enum.Enum):
    AI_CHAT = "AI_CHAT"
    WEB = "WEB"
    ADMIN = "ADMIN"
    API = "API"
    VOICE = "VOICE"


class ConversationChannel(str, enum.Enum):
    WEB = "WEB"
    VOICE = "VOICE"
    WHATSAPP = "WHATSAPP"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    ESCALATED = "ESCALATED"


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"


class DoctorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"


class NotificationChannel(str, enum.Enum):
    SMS = "SMS"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    PUSH = "PUSH"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"


class EscalationType(str, enum.Enum):
    CALL_EMERGENCY = "CALL_EMERGENCY"
    REDIRECT_ED = "REDIRECT_ED"
    NOTIFY_STAFF = "NOTIFY_STAFF"
    CREATE_CALLBACK = "CREATE_CALLBACK"


class AuditActorType(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"
    WORKER = "WORKER"


class ScheduleExceptionType(str, enum.Enum):
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"
    BLOCKED = "BLOCKED"
    EXTENDED = "EXTENDED"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class BloodGroup(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "UNKNOWN"


class DocumentSourceType(str, enum.Enum):
    FAQ = "FAQ"
    POLICY = "POLICY"
    DOCTOR_PROFILE = "DOCTOR_PROFILE"
    PATIENT_INSTRUCTIONS = "PATIENT_INSTRUCTIONS"
    VISITING_HOURS = "VISITING_HOURS"
    INSURANCE = "INSURANCE"
    CONTACT_INFO = "CONTACT_INFO"
    GENERAL = "GENERAL"


class DocumentAccessScope(str, enum.Enum):
    PUBLIC = "PUBLIC"           # Visible to patients via AI
    STAFF = "STAFF"             # Visible to hospital staff only
    INTERNAL = "INTERNAL"       # Internal admin use only
