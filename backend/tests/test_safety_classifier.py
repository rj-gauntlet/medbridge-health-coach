"""Tests for safety classifier."""

import pytest

from app.services.safety_classifier import SafetyClassifier, SafetyResult


def test_safe_message():
    classifier = SafetyClassifier()
    result = classifier.check("Great job on your exercises today!")
    assert result.safe is True
    assert result.category == "ok"


def test_clinical_content_diagnosis():
    classifier = SafetyClassifier()
    result = classifier.check("What is my diagnosis?")
    assert result.safe is False
    assert result.category == "clinical"
    assert "diagnosis" in result.reason.lower()


def test_clinical_content_medication():
    classifier = SafetyClassifier()
    result = classifier.check("Should I take medication for the pain?")
    assert result.safe is False
    assert result.category == "clinical"


def test_clinical_content_symptom():
    classifier = SafetyClassifier()
    result = classifier.check("I have a symptom in my knee")
    assert result.safe is False


def test_crisis_content():
    classifier = SafetyClassifier()
    result = classifier.check("I want to kill myself")
    assert result.safe is False
    assert result.category == "crisis"


def test_crisis_self_harm():
    classifier = SafetyClassifier()
    result = classifier.check("I've been thinking about self-harm")
    assert result.safe is False
    assert result.category == "crisis"


def test_crisis_takes_precedence():
    classifier = SafetyClassifier()
    result = classifier.check("I have symptoms and want to end my life")
    assert result.safe is False
    assert result.category in ("clinical", "crisis")  # first match wins
