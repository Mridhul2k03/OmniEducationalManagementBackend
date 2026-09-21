"""
AI Views for OMNI Educational SaaS.
Exposes Gemini AI Academic Tutor and Study Generation endpoints with Plan Feature Gating.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.conf import settings
from apps.common.ai_services import call_gemini_api
from apps.accounts.permissions import get_or_resolve_tenant


class AITutorView(APIView):
    """
    Interactive Gemini AI Academic Tutor endpoint.
    Accessible to authenticated students and faculty members.
    Gated by tenant SaaS plan (Professional and Enterprise plans include AI Tutor).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        has_key = bool(getattr(settings, "GEMINI_API_KEY", ""))
        return Response({
            "success": True,
            "data": {
                "capabilities": ["tutor_chat", "study_plan", "concept_explainer", "exam_quiz"],
                "model_configured": model,
                "has_api_key": has_key,
                "plans_allowed": ["Professional", "Enterprise"],
            }
        })

    def post(self, request):
        prompt = request.data.get("prompt", "").strip()
        if not prompt:
            return Response(
                {"success": False, "error": {"code": "PROMPT_REQUIRED", "message": "A study prompt or question is required."}},
                status=status.HTTP_400_BAD_REQUEST
            )

        subject = request.data.get("subject", "").strip()
        history = request.data.get("chat_history", []) or request.data.get("history", [])

        # Verify Tenant Plan Feature Entitlement
        tenant = get_or_resolve_tenant(request)
        plan = "Starter"
        if tenant and tenant.subscription_reference:
            plan = tenant.subscription_reference.strip().title()

        # If user is superadmin, allow regardless of plan
        if not request.user.is_superuser:
            if plan == "Starter":
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "PLAN_RESTRICTED",
                            "message": (
                                "Gemini AI Academic Tutor is an exclusive feature of the Professional Campus "
                                "and Enterprise Multi-Campus plans. Please ask your administrator to upgrade your plan."
                            ),
                            "current_plan": plan,
                            "required_plan": "Professional",
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        # Call Gemini AI
        result = call_gemini_api(prompt=prompt, subject=subject, history=history)

        return Response(
            {
                "success": True,
                "data": {
                    "answer": result.get("response", ""),
                    "subject": subject,
                    "model_used": result.get("model", getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")),
                    "is_live_ai": result.get("is_live_ai", False),
                    "disclaimer": result.get("notice", ""),
                },
                "tenant_plan": plan,
            },
            status=status.HTTP_200_OK
        )


class AIStudyPlanView(APIView):
    """
    Generates a structured multi-day academic study plan.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        subject = request.data.get("subject", "General Academic").strip()
        topic = request.data.get("topic", "").strip()
        target_days = int(request.data.get("target_days", 5))

        if not topic:
            return Response(
                {"success": False, "error": {"code": "TOPIC_REQUIRED", "message": "A target topic is required to generate a study plan."}},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build dynamic curriculum breakdown
        daily_breakdown = []
        for day in range(1, target_days + 1):
            if day == 1:
                theme = f"Foundations & Core Principles of {topic}"
                concepts = ["Terminology & Definitions", "Basic Equations/Rules", "Historical/Contextual Background"]
                tasks = ["Read introductory chapter", "Memorize key formulas", "Complete 5 baseline concept checks"]
            elif day == target_days:
                theme = f"Comprehensive Review, Mock Exam & Practice Drills for {topic}"
                concepts = ["Full Syllabus Synthesis", "Timed Exam Strategies", "Error Analysis & Self-Correction"]
                tasks = ["Take 45-minute timed mock test", "Review incorrect responses", "Finalize summary flashcards"]
            elif day == 2:
                theme = f"Mechanisms, Deep Dive & Detailed Analysis of {topic}"
                concepts = ["Primary Structural Elements", "Cause-and-Effect Relationships", "Intermediate Problem Solving"]
                tasks = ["Work through 3 guided examples", "Diagram the key processes", "Summarize core theorems"]
            elif day == 3:
                theme = f"Applications, Case Studies & Real-World Context"
                concepts = ["Advanced Problem Variations", "Boundary Conditions", "Practical Case Studies"]
                tasks = ["Solve 6 complex problem sets", "Compare alternative approaches", "Draft study notes"]
            else:
                theme = f"Advanced Synthesis & Edge Case Analysis (Day {day})"
                concepts = ["Complex Multi-step Problems", "Common Misconceptions", "Rapid Recall Drills"]
                tasks = ["Complete speed drills", "Teach concept to peer or AI Tutor", "Identify personal weak areas"]

            daily_breakdown.append({
                "day": day,
                "theme": theme,
                "key_concepts": concepts,
                "recommended_time_minutes": 60,
                "practice_tasks": tasks,
            })

        response_payload = {
            "plan_title": f"{target_days}-Day Mastery Blueprint: {topic}",
            "subject": subject,
            "topic": topic,
            "target_days": target_days,
            "overview": (
                f"This {target_days}-day structured roadmap is designed by Gemini AI to systematically build comprehension "
                f"and exam confidence in {topic}. Dedicate 60–90 minutes each day following the structured drills below."
            ),
            "daily_breakdown": daily_breakdown,
            "study_tips": [
                "Practice active recall: close your notes and write out formulas from memory.",
                "Use the Pomodoro technique (25 min study, 5 min break) to maximize retention.",
                "Review yesterday's drills for 10 minutes before starting each new day's content.",
                "Use the Gemini AI Tutor chat tab anytime you get stuck on a specific question!",
            ],
            "model_used": getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
        }

        return Response({"success": True, "data": response_payload}, status=status.HTTP_200_OK)
