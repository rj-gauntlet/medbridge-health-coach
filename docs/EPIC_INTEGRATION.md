# Epic / EMR Integration

This document describes how the MedBridge AI Health Coach can integrate with Epic (or other EMRs) to receive patient and program data.

## Overview

- **Patient Sync**: Epic pushes patient demographics when a patient is enrolled in the AI coach program.
- **Program Sync**: Epic pushes HEP (Home Exercise Program) assignments when a clinician assigns a program to a patient.

## Stub Endpoints

The following endpoints are implemented as stubs and return `{"status": "received"}`. In production, they would:

1. Validate webhook signatures
2. Create/update patient records
3. Link programs to patient threads
4. Trigger consent flows

### POST /api/epic/patient

Receive patient data from Epic.

**Request body:**
```json
{
  "patient_id": "epic-mrn-12345",
  "mrn": "12345",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

**Production behavior:**
- Create or update patient in local store
- Set consent status from Epic's consent capture
- Optionally trigger onboarding outreach

### POST /api/epic/program

Receive HEP program assignment from Epic.

**Request body:**
```json
{
  "patient_id": "epic-mrn-12345",
  "program_id": "hep-xyz",
  "exercises": ["Knee extension", "Quad sets", "Heel slides"],
  "notes": "3x10 each, as tolerated"
}
```

**Production behavior:**
- Create thread if none exists
- Store program summary for the coach to reference
- Update `program_summary` in agent context

## Webhook Configuration

Epic would be configured to call these endpoints on:

- **Patient enrollment**: When a patient is added to the AI coach program in MyChart or clinician workflow
- **Program assignment**: When a clinician assigns an HEP to a patient

## Security

- Use HMAC or OAuth 2.0 for webhook authentication
- Validate origin IP allowlist
- Log all incoming payloads for audit
