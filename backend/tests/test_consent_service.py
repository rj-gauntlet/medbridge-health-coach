"""Tests for consent service."""

import pytest

from app.services.consent_service import MockConsentService


def test_default_all_allowed():
    svc = MockConsentService(default_allowed=True)
    assert svc.can_interact("patient-001") is True
    assert svc.can_interact("patient-069") is True


def test_denied_patient_ids():
    svc = MockConsentService(default_allowed=True, denied_patient_ids={"patient-999"})
    assert svc.can_interact("patient-001") is True
    assert svc.can_interact("patient-999") is False


def test_default_denied_all():
    svc = MockConsentService(default_allowed=False)
    assert svc.can_interact("patient-001") is False


def test_denied_overrides_default_denied():
    svc = MockConsentService(default_allowed=False, denied_patient_ids=set())
    assert svc.can_interact("patient-001") is False
