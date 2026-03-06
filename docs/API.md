# API Documentation

The MedBridge AI Health Coach exposes a REST API. Interactive docs are available when the server is running:

- **Swagger UI**: http://127.0.0.1:8080/docs
- **ReDoc**: http://127.0.0.1:8080/redoc

---

## Endpoints

### `GET /health`

Health check.

**Response:** `{"status": "ok"}`

---

### `GET /api/thread`

Get the full conversation for a patient, including any scheduled check-ins added by the scheduler.

**Query parameters:**

| Name        | Type   | Required | Description                          |
|-------------|--------|----------|--------------------------------------|
| `patient_id`| string | Yes      | Patient identifier                   |
| `thread_id` | string | No       | Thread ID (if known)                 |

**Response:**
```json
{
  "thread_id": "uuid-string",
  "phase": "ACTIVE",
  "messages": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello! How can I help?"}
  ]
}
```

---

### `POST /api/chat`

Send a message to the coach and receive a response.

**Request body:**
```json
{
  "patient_id": "patient-001",
  "message": "I want to do my exercises 3 times a week",
  "thread_id": "uuid-string"
}
```

| Field       | Type   | Required | Description                    |
|-------------|--------|----------|--------------------------------|
| `patient_id`| string | Yes      | Patient identifier             |
| `message`   | string | Yes      | The user's message             |
| `thread_id` | string | No       | Thread ID (for continuing chat)|

**Response:**
```json
{
  "reply": "That's a great goal! ...",
  "thread_id": "uuid-string",
  "phase": "ONBOARDING",
  "blocked": false,
  "error": null
}
```

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| `reply`  | string | The coach's response                             |
| `thread_id` | string | Thread ID for subsequent messages            |
| `phase`  | string | Current phase (PENDING, ONBOARDING, ACTIVE, RE_ENGAGING, DORMANT) |
| `blocked`| bool   | True if message was blocked (e.g. consent, safety) |
| `error`  | string | Error code if blocked (e.g. "consent_required")  |

---

## Phases

| Phase      | Description                                                |
|------------|------------------------------------------------------------|
| PENDING    | Thread created, awaiting first interaction                 |
| ONBOARDING | Goal-setting flow (welcome, extract goal, confirm)         |
| ACTIVE     | Goal set; normal follow-ups and scheduled check-ins        |
| RE_ENGAGING| Patient returned after being dormant; warm re-engagement   |
| DORMANT    | No response after 3 nudges; clinician alerted              |
