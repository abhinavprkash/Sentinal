from enum import Enum


class PipelineEvent(str, Enum):
    INCIDENT_RECEIVED = "IncidentReceived"
    TRIAGE_COMPLETED = "TriageCompleted"
    INVESTIGATION_COMPLETED = "InvestigationCompleted"
    PATCH_GENERATED = "PatchGenerated"
    VERIFICATION_COMPLETED = "VerificationCompleted"
    APPROVAL_PACKAGE_READY = "ApprovalPackageReady"
    INCIDENT_ESCALATED = "IncidentEscalated"
    INCIDENT_APPROVED = "IncidentApproved"
    INCIDENT_REJECTED = "IncidentRejected"
    RETRY_TRIGGERED = "RetryTriggered"
