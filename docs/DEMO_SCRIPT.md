# MedBridge AI Health Coach — Demo Script

Use this script for presentation rehearsal or recording a walkthrough.

## Pre-Demo Setup

1. **Start the backend**
   ```bash
   cd backend
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
   ```

2. **Enable demo mode** (1 minute = 1 day for scheduling): Add to `.env`:
   ```
   SCHEDULER_DAY_SECONDS=60
   ```

3. **Open the app** in your browser: http://127.0.0.1:8080

---

## Demo Flow (~5–7 minutes)

### 1. Chat & Onboarding (2 min)

- Load patient `patient-001` (or enter another ID and click **Load**).
- Say: *"Hi, I'm ready to start my knee exercises."*
- Coach welcomes and asks for a goal.
- Reply: *"I want to do my exercises 3 times a week."*
- Coach extracts the goal and confirms. Continue until goal is set.
- **Show:** Phase moves to ACTIVE, goal appears in the status bar.

### 2. PROs & Streak (1 min)

- Coach may ask for pain/difficulty ratings. Reply: *"Pain was 3, difficulty was 5."*
- **Show:** PROs button appears; click it to see stored PROs.
- If engaged today, **streak** shows in the status bar.

### 3. Coach Personality (30 sec)

- Change the **Personality** dropdown (Encouraging / Direct / Calm).
- Send another message. Note the tone difference.

### 4. Exercise Library (1 min)

- Click **View exercises** in the header.
- Scroll through Knee Extension, Quad Sets, Heel Slides with animated demos.
- Click **← Back to Chat** to return.

### 5. Clinician Dashboard (1–2 min)

- Click **Clinician Dashboard**.
- View patient table: phase, goal, at-risk flag, conversation summaries.
- Click a row to expand details: goal, PROs, full summary.
- (Optional) Load a different patient, return to chat, then refresh the dashboard to show multiple patients.)

### 6. Safety & Edge Cases (1 min)

- Return to chat. Try: *"Should I take ibuprofen for my knee pain?"*
- Coach redirects to the care team and does not give medical advice.
- (Optional) Try a clinical-style question to show the safety classifier.)

---

## Quick Reference

| Feature             | Where to show                         |
|---------------------|----------------------------------------|
| Onboarding          | Chat, first 3–4 messages               |
| Goal + phase        | Status bar, phase badge                |
| PROs                | Chat → PROs button in status bar       |
| Streak              | Status bar when engaged today          |
| Personality         | Dropdown in header                     |
| Exercise library    | "View exercises" link                  |
| Dashboard           | "Clinician Dashboard" link             |
| Safety redirect     | Ask clinical question in chat          |

---

## Troubleshooting

- **No reply:** Check `OPENAI_API_KEY` in `.env`.
- **Scheduler not firing:** Ensure `SCHEDULER_DAY_SECONDS=60` and wait ~1 minute for Day 2 check-in.
- **Favicon or logos missing:** Confirm `frontend/assets/` and `frontend/mockups/assets/` exist.
