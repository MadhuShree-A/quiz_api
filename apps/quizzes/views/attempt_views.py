import logging
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from ..models import Quiz, QuizAttempt, UserAnswer, Question
from ..serializers import (
    AttemptListSerializer, AttemptDetailSerializer,
    UserAnswerSubmitSerializer, BulkAnswerSubmitSerializer,
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_attempt(request, quiz_id):
    """
    POST /api/v1/quizzes/<quiz_id>/attempt/
    Start a new attempt. If the quiz doesn't allow retakes and the user
    already has a completed attempt, returns 409.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, status=Quiz.Status.PUBLISHED)

    if not quiz.is_public and quiz.creator != request.user:
        return Response(
            {'error': {'code': 'forbidden', 'message': 'This quiz is private.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check for active (in-progress) attempt
    active = QuizAttempt.objects.filter(
        user=request.user, quiz=quiz, status=QuizAttempt.Status.IN_PROGRESS
    ).first()
    if active:
        return Response(
            {
                'attempt_id': str(active.id),
                'message': 'You already have an active attempt for this quiz.',
                'started_at': active.started_at,
            },
            status=status.HTTP_200_OK,
        )

    # Check retake policy
    if not quiz.allow_retake:
        already_completed = QuizAttempt.objects.filter(
            user=request.user, quiz=quiz, status=QuizAttempt.Status.COMPLETED
        ).exists()
        if already_completed:
            return Response(
                {'error': {'code': 'conflict', 'message': 'Retakes are not allowed for this quiz.'}},
                status=status.HTTP_409_CONFLICT,
            )

    attempt = QuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        status=QuizAttempt.Status.IN_PROGRESS,
        difficulty_at_attempt=quiz.difficulty,
    )
    return Response(
        {
            'attempt_id': str(attempt.id),
            'quiz_id': str(quiz.id),
            'quiz_title': quiz.title,
            'question_count': quiz.question_count,
            'time_limit_minutes': quiz.time_limit_minutes,
            'started_at': attempt.started_at,
            'expires_at': (
                attempt.started_at + timezone.timedelta(minutes=quiz.time_limit_minutes)
                if quiz.time_limit_minutes else None
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_answer(request, attempt_id):
    """
    POST /api/v1/attempts/<attempt_id>/answer/
    Submit a single answer. Allows updating an answer before final submission.
    """
    attempt = get_object_or_404(
        QuizAttempt, id=attempt_id, user=request.user, status=QuizAttempt.Status.IN_PROGRESS
    )

    if attempt.is_timed_out:
        attempt.status = QuizAttempt.Status.TIMED_OUT
        attempt.save(update_fields=['status'])
        return Response(
            {'error': {'code': 'timed_out', 'message': 'Your attempt has timed out.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = UserAnswerSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    question = get_object_or_404(Question, id=data['question_id'], quiz=attempt.quiz)

    answer, created = UserAnswer.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={
            'selected_answer': data['selected_answer'],
            'time_taken_seconds': data.get('time_taken_seconds'),
        },
    )

    return Response({
        'question_id': str(question.id),
        'answer_saved': True,
        'is_correct': answer.is_correct,
        'points_earned': answer.points_earned,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_submit_answers(request, attempt_id):
    """
    POST /api/v1/attempts/<attempt_id>/answers/bulk/
    Submit all answers at once (fire-and-forget client style).
    """
    attempt = get_object_or_404(
        QuizAttempt, id=attempt_id, user=request.user, status=QuizAttempt.Status.IN_PROGRESS
    )

    serializer = BulkAnswerSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    answers_data = serializer.validated_data['answers']

    questions_map = {
        str(q.id): q
        for q in attempt.quiz.questions.all()
    }

    with transaction.atomic():
        for ans in answers_data:
            qid = str(ans['question_id'])
            question = questions_map.get(qid)
            if not question:
                continue
            UserAnswer.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    'selected_answer': ans['selected_answer'],
                    'time_taken_seconds': ans.get('time_taken_seconds'),
                },
            )

    return Response({'answers_saved': len(answers_data)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_attempt(request, attempt_id):
    """
    POST /api/v1/attempts/<attempt_id>/submit/
    Finalise the attempt: score it and return detailed results.
    """
    attempt = get_object_or_404(
        QuizAttempt, id=attempt_id, user=request.user
    )

    if attempt.status not in (QuizAttempt.Status.IN_PROGRESS, QuizAttempt.Status.TIMED_OUT):
        return Response(
            {'error': {'code': 'conflict', 'message': f'Attempt is already {attempt.status}.'}},
            status=status.HTTP_409_CONFLICT,
        )

    if attempt.is_timed_out:
        attempt.status = QuizAttempt.Status.TIMED_OUT

    attempt.complete()  # scores + saves + updates profile stats

    return Response(AttemptDetailSerializer(attempt).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attempt_results(request, attempt_id):
    """
    GET /api/v1/attempts/<attempt_id>/results/
    Get the full scored results for a submitted attempt.
    """
    attempt = get_object_or_404(
        QuizAttempt.objects.prefetch_related(
            'answers__question'
        ).select_related('quiz'),
        id=attempt_id,
        user=request.user,
    )

    if attempt.status == QuizAttempt.Status.IN_PROGRESS:
        return Response(
            {'error': {'code': 'bad_request', 'message': 'Attempt has not been submitted yet.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(AttemptDetailSerializer(attempt).data)


class MyAttemptsView(generics.ListAPIView):
    """
    GET /api/v1/attempts/  — current user's attempt history.
    Supports ?quiz=<id>, ?status=completed, ordering=-started_at etc.
    """
    serializer_class = AttemptListSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'quiz']
    ordering_fields = ['started_at', 'score_percentage']
    ordering = ['-started_at']

    def get_queryset(self):
        return QuizAttempt.objects.filter(
            user=self.request.user
        ).select_related('quiz').order_by('-started_at')
