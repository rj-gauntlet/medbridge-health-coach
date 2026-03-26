"""Coach service: orchestrates consent, LangGraph invocation, safety check, persistence."""

import uuid
from datetime import datetime
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import build_graph
from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread
from app.repositories.interfaces import IThreadRepository
from app.services.consent_service import IConsentService
from app.services.safety_classifier import SafetyClassifier


class CoachService:
    """Main orchestrator for coach interactions."""

    def __init__(
        self,
        thread_repo: IThreadRepository,
        consent_service: IConsentService,
        pro_repo=None,
        alert_repo=None,
        safety_classifier: SafetyClassifier | None = None,
    ):
        self.thread_repo = thread_repo
        self.consent_service = consent_service
        self.pro_repo = pro_repo
        self.alert_repo = alert_repo
        self.safety_classifier = safety_classifier or SafetyClassifier()
        self._graph = None

    def _get_graph(self, thread_id: str = "", patient_id: str = ""):
        # Rebuild graph each time to pass thread context to alert tool closure
        return build_graph(thread_repo=self.thread_repo, pro_repo=self.pro_repo, alert_repo=self.alert_repo, thread_id=thread_id, patient_id=patient_id)

    def process_message(self, patient_id: str, user_message: str, thread_id: str | None = None, personality: str | None = None) -> dict:
        """
        Process a patient message and return the coach response.
        Returns: {"reply": str, "thread_id": str, "phase": str, "blocked": bool, "error": str | None}
        """
        if not self.consent_service.can_interact(patient_id):
            return {
                "reply": "Please log into MedBridge Go and consent to coach outreach to continue.",
                "thread_id": thread_id or "",
                "phase": CoachPhase.PENDING.value,
                "blocked": True,
                "error": "consent_required",
            }

        thread = self._get_or_create_thread(patient_id, thread_id)
        thread_id = thread.thread_id
        if personality and personality in ("encouraging", "direct", "calm"):
            thread.personality = personality
            self.thread_repo.save(thread)

        # DORMANT → RE_ENGAGING when patient returns
        if thread.phase == CoachPhase.DORMANT:
            thread.phase = CoachPhase.RE_ENGAGING
            self.thread_repo.update_phase(thread_id, CoachPhase.RE_ENGAGING)
            self.thread_repo.update_unanswered_count(thread_id, 0)

        # Ensure we're in ONBOARDING if still PENDING
        if thread.phase == CoachPhase.PENDING:
            thread.phase = CoachPhase.ONBOARDING
            self.thread_repo.update_phase(thread_id, CoachPhase.ONBOARDING)

        # Convert to LangGraph state (LangChain message objects)
        lc_messages = []
        for m in thread.messages:
            if m.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=m.content))
        lc_messages.append(HumanMessage(content=user_message))

        personality = getattr(thread, "personality", None) or "encouraging"
        agent_state = {
            "messages": lc_messages,
            "phase": thread.phase.value,
            "goal": {"description": thread.goal.description, "frequency": thread.goal.frequency} if thread.goal else None,
            "thread_id": thread_id,
            "patient_id": patient_id,
            "program_summary": "Knee exercises: stretches, quad sets, heel slides. 3x10 each.",
            "interaction_type": "user_message",
            "personality": personality,
        }

        graph = self._get_graph(thread_id=thread_id, patient_id=patient_id)
        result = graph.invoke(agent_state)

        # Extract assistant reply from last AI message
        reply = self._extract_reply(result.get("messages", []))
        if not reply:
            reply = "I'm here to help. Could you tell me a bit more about your exercise goals?"

        # Safety check with retry
        safety = self.safety_classifier.check(reply)
        if not safety.safe:
            if safety.category == "crisis":
                # Crisis: no retry, use fallback and alert
                reply = "I'd like to connect you with your care team right away. Please reach out to your clinician or a mental health professional."
            else:
                # Clinical: retry once with augmented prompt
                retry_messages = list(result.get("messages", []))
                retry_messages.append(
                    HumanMessage(
                        content="[System: Your previous response was flagged. Please reword to be supportive and encouraging without any clinical or medical content. Redirect the patient to their care team for medical questions.]"
                    )
                )
                retry_state = {**agent_state, "messages": retry_messages}
                retry_result = graph.invoke(retry_state)
                retry_reply = self._extract_reply(retry_result.get("messages", []))
                if retry_reply:
                    retry_safety = self.safety_classifier.check(retry_reply)
                    if retry_safety.safe:
                        reply = retry_reply
                        safety = retry_safety
                    else:
                        reply = "I'd like to connect you with your care team for that. Please reach out to your clinician directly."
                else:
                    reply = "I'd like to connect you with your care team for that. Please reach out to your clinician directly."

        # Persist user message and assistant reply
        self.thread_repo.add_message(thread_id, Message(role=MessageRole.USER, content=user_message))
        self.thread_repo.add_message(thread_id, Message(role=MessageRole.ASSISTANT, content=reply))

        # Reset unanswered count when user replies
        self.thread_repo.update_unanswered_count(thread_id, 0)

        # Check for set_goal tool call and persist goal
        new_goal = self._extract_goal_from_result(result)

        if new_goal:
            self.thread_repo.update_goal(thread_id, new_goal)
            self.thread_repo.update_phase(thread_id, CoachPhase.ACTIVE)
            self.thread_repo.update_goal_confirmed_at(thread_id, datetime.utcnow())

        # Update last interaction and last coach message (for disengagement)
        thread = self.thread_repo.get(thread_id)
        if thread:
            now = datetime.utcnow()
            thread.last_interaction_at = now
            thread.last_coach_message_at = now
            self.thread_repo.save(thread)

        return {
            "reply": reply,
            "thread_id": thread_id,
            "phase": thread.phase.value if thread else CoachPhase.ONBOARDING.value,
            "blocked": not safety.safe,
            "error": None,
        }

    def _get_or_create_thread(self, patient_id: str, thread_id: str | None) -> Thread:
        if thread_id:
            thread = self.thread_repo.get(thread_id)
            if thread:
                return thread
        thread = self.thread_repo.get_by_patient(patient_id)
        if thread:
            return thread
        thread = Thread(
            thread_id=str(uuid.uuid4()),
            patient_id=patient_id,
            phase=CoachPhase.PENDING,
        )
        self.thread_repo.save(thread)
        return thread

    def _extract_reply(self, messages: list) -> str:
        for m in reversed(messages):
            if isinstance(m, AIMessage) and m.content:
                return m.content if isinstance(m.content, str) else str(m.content)
        return ""

    def _extract_goal_from_result(self, result: dict) -> Goal | None:
        messages = result.get("messages", [])
        for m in reversed(messages):
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    if tc.get("name") == "set_goal":
                        args = tc.get("args", {})
                        return Goal(
                            description=args.get("description", ""),
                            frequency=args.get("frequency"),
                        )
        return None

    def process_scheduled_checkin(self, thread_id: str, day: int) -> None:
        """Send a scheduled Day 2, 5, or 7 check-in. Called by scheduler."""
        thread = self.thread_repo.get(thread_id)
        if not thread or not thread.goal or not self.consent_service.can_interact(thread.patient_id):
            return
        tone_map = {2: "check-in", 5: "nudge", 7: "celebration"}
        tone = tone_map.get(day, "check-in")

        lc_messages = []
        for m in thread.messages:
            if m.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=m.content))
        lc_messages.append(HumanMessage(content=f"[Scheduled Day {day} check-in - {tone}]"))

        personality = getattr(thread, "personality", None) or "encouraging"
        agent_state = {
            "messages": lc_messages,
            "phase": thread.phase.value,
            "goal": {"description": thread.goal.description, "frequency": thread.goal.frequency},
            "thread_id": thread_id,
            "patient_id": thread.patient_id,
            "program_summary": "Knee exercises: stretches, quad sets, heel slides. 3x10 each.",
            "interaction_type": "scheduled_checkin",
            "scheduled_checkin_day": day,
            "tone": tone,
            "personality": personality,
        }

        graph = self._get_graph(thread_id=thread_id, patient_id=thread.patient_id)
        result = graph.invoke(agent_state)
        reply = self._extract_reply(result.get("messages", []))
        if not reply:
            reply = f"Hi! Just checking in on your exercise goal. How's it going?"

        self.thread_repo.add_message(thread_id, Message(role=MessageRole.ASSISTANT, content=reply))
        checkins = list(thread.checkins_sent or [])
        if day not in checkins:
            checkins.append(day)
            checkins.sort()
        self.thread_repo.update_checkins_sent(thread_id, checkins)
        now = datetime.utcnow()
        t = self.thread_repo.get(thread_id)
        if t:
            t.last_coach_message_at = now
            t.last_interaction_at = now
            self.thread_repo.save(t)

    def process_disengagement_nudge(self, thread_id: str) -> None:
        """Send nudge for unanswered messages, or alert clinician and go DORMANT at 3."""
        thread = self.thread_repo.get(thread_id)
        if not thread or not self.consent_service.can_interact(thread.patient_id):
            return

        next_count = thread.unanswered_count + 1
        if next_count >= 3:
            # Alert clinician and transition to DORMANT
            if self.alert_repo:
                from app.models.domain import ClinicianAlert
                self.alert_repo.add(ClinicianAlert(
                    thread_id=thread_id,
                    patient_id=thread.patient_id,
                    reason="Patient has not responded after 3 coach messages",
                    urgency="normal",
                ))
            self.thread_repo.update_unanswered_count(thread_id, 3)
            self.thread_repo.update_phase(thread_id, CoachPhase.DORMANT)
            # Add a final message
            msg = "I've reached out a few times. When you're ready to get back on track, just send a message—I'm here for you."
            self.thread_repo.add_message(thread_id, Message(role=MessageRole.ASSISTANT, content=msg))
        else:
            # Send nudge
            lc_messages = []
            for m in thread.messages:
                if m.role == MessageRole.USER:
                    lc_messages.append(HumanMessage(content=m.content))
                elif m.role == MessageRole.ASSISTANT:
                    lc_messages.append(AIMessage(content=m.content))
            lc_messages.append(HumanMessage(content="[Disengagement nudge - no user reply]"))

            personality = getattr(thread, "personality", None) or "encouraging"
            agent_state = {
                "messages": lc_messages,
                "phase": thread.phase.value,
                "goal": {"description": thread.goal.description, "frequency": thread.goal.frequency} if thread.goal else None,
                "thread_id": thread_id,
                "patient_id": thread.patient_id,
                "program_summary": "Knee exercises: stretches, quad sets, heel slides. 3x10 each.",
                "interaction_type": "user_message",
                "personality": personality,
            }

            graph = self._get_graph(thread_id=thread_id, patient_id=thread.patient_id)
            result = graph.invoke(agent_state)
            reply = self._extract_reply(result.get("messages", []))
            if not reply:
                reply = "Hey! Just wanted to check in—how are your exercises going? I'm here when you need a nudge."

            self.thread_repo.add_message(thread_id, Message(role=MessageRole.ASSISTANT, content=reply))
            self.thread_repo.update_unanswered_count(thread_id, next_count)
            now = datetime.utcnow()
            t = self.thread_repo.get(thread_id)
            if t:
                t.last_coach_message_at = now
                t.last_interaction_at = now
                self.thread_repo.save(t)

    def summarize_conversation(self, thread_id: str) -> None:
        """Generate a brief summary of the conversation for clinicians."""
        thread = self.thread_repo.get(thread_id)
        if not thread or len(thread.messages) < 2:
            return
        from langchain_openai import ChatOpenAI
        from app.config import get_settings
        settings = get_settings()
        llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0.3)
        recent = thread.messages[-20:]
        text = "\n".join([f"{m.role.value}: {m.content[:200]}" for m in recent])
        prompt = f"Summarize this patient-coach conversation in 2-3 sentences for a clinician. Focus on: goal, adherence, concerns, pain/difficulty.\n\n{text}"
        try:
            summary = llm.invoke(prompt).content
            thread.conversation_summary = summary
            thread.last_summary_at = datetime.utcnow()
            self.thread_repo.save(thread)
        except Exception:
            pass
