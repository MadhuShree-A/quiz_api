from django.urls import path
from .views import (
    my_dashboard, quiz_analytics, quiz_question_analytics,
    leaderboard, admin_overview,
)

urlpatterns = [
    path('dashboard/', my_dashboard, name='analytics-dashboard'),
    path('leaderboard/', leaderboard, name='analytics-leaderboard'),
    path('admin/overview/', admin_overview, name='analytics-admin-overview'),
    path('quizzes/<uuid:quiz_id>/', quiz_analytics, name='analytics-quiz'),
    path('quizzes/<uuid:quiz_id>/questions/', quiz_question_analytics, name='analytics-quiz-questions'),
]
