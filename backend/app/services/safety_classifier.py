"""Safety classifier: pre-delivery check for clinical content and crisis signals."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class SafetyResult:
    """Result of safety check."""

    safe: bool
    reason: str | None = None
    category: Literal["ok", "clinical", "crisis"] = "ok"


class SafetyClassifier:
    """Checks messages before delivery. Clinical/crisis content triggers redirect/alert."""

    def check(self, message: str) -> SafetyResult:
        """Check if message is safe to deliver. Returns SafetyResult."""
        msg_lower = message.lower()
        # Crisis keywords - escalate immediately
        crisis_terms = ["suicide", "kill myself", "end my life", "self-harm", "hurt myself"]
        for term in crisis_terms:
            if term in msg_lower:
                return SafetyResult(safe=False, reason=f"crisis signal: {term}", category="crisis")

        # Clinical keywords - redirect to care team
        clinical_terms = [
            "diagnosis", "diagnose", "symptom", "medication", "prescription",
            "treatment plan", "doctor said", "doctor told", "clinician said",
            "pain level", "level of pain", "how much it hurts",
            "x-ray", "mri", "ct scan", "blood test",
        ]
        for term in clinical_terms:
            if term in msg_lower:
                return SafetyResult(safe=False, reason=f"clinical content: {term}", category="clinical")

        return SafetyResult(safe=True)
