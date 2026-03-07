"""Epic/EMR integration stub endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/epic", tags=["epic"])


class EpicPatientPayload(BaseModel):
    """Stub: patient data from Epic/MyChart."""

    patient_id: str
    mrn: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class EpicProgramPayload(BaseModel):
    """Stub: HEP program data from Epic."""

    patient_id: str
    program_id: str | None = None
    exercises: list[str] = []
    notes: str | None = None


@router.post("/patient")
def receive_patient(payload: EpicPatientPayload) -> dict:
    """Receive patient sync from Epic. In production: create/update patient and consent."""
    return {"status": "received", "patient_id": payload.patient_id}


@router.post("/program")
def receive_program(payload: EpicProgramPayload) -> dict:
    """Receive HEP program assignment from Epic. In production: link program to patient thread."""
    return {"status": "received", "patient_id": payload.patient_id}
