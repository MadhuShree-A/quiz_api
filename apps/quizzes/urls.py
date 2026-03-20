from django.urls import path
from .views.quiz_views import (
    QuizListView, QuizDetailView, QuizCreateView,
    QuizUpdateView, QuizDeleteView, MyQuizzesView, regenerate_quiz,
)
from .views.attempt_views import (
    start_attempt, submit_answer, bulk_submit_answers,
    submit_attempt, attempt_results, MyAttemptsView,
)

urlpatterns = [
    # ── Quiz CRUD ──────────────────────────────────────────────────────────────
    path('', QuizListView.as_view(), name='quiz-list'),
    path('mine/', MyQuizzesView.as_view(), name='quiz-mine'),
    path('create/', QuizCreateView.as_view(), name='quiz-create'),
    path('<uuid:id>/', QuizDetailView.as_view(), name='quiz-detail'),
    path('<uuid:id>/edit/', QuizUpdateView.as_view(), name='quiz-update'),
    path('<uuid:id>/delete/', QuizDeleteView.as_view(), name='quiz-delete'),
    path('<uuid:id>/regenerate/', regenerate_quiz, name='quiz-regenerate'),

    # ── Attempt flow ───────────────────────────────────────────────────────────
    path('<uuid:quiz_id>/attempt/', start_attempt, name='attempt-start'),

    # ── Attempt actions ────────────────────────────────────────────────────────
    path('attempts/', MyAttemptsView.as_view(), name='attempt-list'),
    path('attempts/<uuid:attempt_id>/answer/', submit_answer, name='attempt-answer'),
    path('attempts/<uuid:attempt_id>/answers/bulk/', bulk_submit_answers, name='attempt-bulk-answer'),
    path('attempts/<uuid:attempt_id>/submit/', submit_attempt, name='attempt-submit'),
    path('attempts/<uuid:attempt_id>/results/', attempt_results, name='attempt-results'),
]
