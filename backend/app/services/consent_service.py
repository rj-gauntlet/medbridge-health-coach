"""Consent gate: verifies patient has logged into MedBridge Go and consented to outreach."""

from abc import ABC, abstractmethod


class IConsentService(ABC):
    """Abstract interface for consent verification."""

    @abstractmethod
    def can_interact(self, patient_id: str) -> bool:
        """Returns True if the patient has logged in and consented to coach outreach."""
        pass


class MockConsentService(IConsentService):
    """Mock implementation. For demo: all patients are consented.
    Can be configured to simulate denied consent for testing."""

    def __init__(self, default_allowed: bool = True, denied_patient_ids: set | None = None):
        self.default_allowed = default_allowed
        self.denied_patient_ids = denied_patient_ids or set()

    def can_interact(self, patient_id: str) -> bool:
        if patient_id in self.denied_patient_ids:
            return False
        return self.default_allowed
