from django.urls import path
from apps.common.ai_views import AITutorView, AIStudyPlanView

urlpatterns = [
    path("tutor/", AITutorView.as_view(), name="ai-tutor"),
    path("study-plan/", AIStudyPlanView.as_view(), name="ai-study-plan"),
]
