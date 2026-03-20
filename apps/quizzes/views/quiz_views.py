import logging
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from ..models import Quiz, Question
from ..serializers import (
    QuizListSerializer, QuizDetailSerializer,
    QuizCreateSerializer, QuizUpdateSerializer,
)
from apps.quizzes.ai_service import generate_quiz_questions,AIServiceError
from quiz_api.permissions import IsOwnerOrAdmin

logger = logging.getLogger(__name__)


class AIGenerationThrottle(UserRateThrottle):
    scope = 'ai_generation'


class QuizListView(generics.ListAPIView):
    """GET /api/v1/quizzes/ — all published public quizzes."""
    serializer_class = QuizListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['difficulty', 'topic', 'is_public']
    search_fields = ['title', 'topic', 'tags']
    ordering_fields = ['created_at', 'avg_score', 'attempt_count', 'difficulty']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Quiz.objects
            .filter(status=Quiz.Status.PUBLISHED, is_public=True)
            .select_related('creator')
            .order_by('-created_at')
        )


class MyQuizzesView(generics.ListAPIView):
    """GET /api/v1/quizzes/mine/ — quizzes created by the current user."""
    serializer_class = QuizListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Quiz.objects.filter(creator=self.request.user).order_by('-created_at')


class QuizDetailView(generics.RetrieveAPIView):
    """GET /api/v1/quizzes/<id>/ — quiz detail with questions (no correct answers)."""
    serializer_class = QuizDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        qs = Quiz.objects.prefetch_related('questions').select_related('creator')
        if user.is_authenticated and (user.is_staff or user.role == 'admin'):
            return qs
        return qs.filter(status=Quiz.Status.PUBLISHED)


class QuizCreateView(generics.CreateAPIView):
    """
    POST /api/v1/quizzes/create/
    Creates a quiz and calls AI to generate questions. Throttled: 10/hour.
    """
    serializer_class = QuizCreateSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIGenerationThrottle]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        data.pop('question_types', None)
        data.pop('additional_context', None)

        quiz = Quiz.objects.create(
            creator=request.user,
            status=Quiz.Status.GENERATING,
            **data,
        )

        try:
            questions_data = generate_quiz_questions(
                topic=quiz.topic,
                count=quiz.question_count,
                difficulty=quiz.difficulty,
            )
        except AIServiceError as exc:
            quiz.status = Quiz.Status.FAILED
            quiz.generation_error = str(exc)
            quiz.save(update_fields=['status', 'generation_error'])
            return Response(
                {'error': {'code': 'ai_generation_failed', 'message': str(exc)}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        questions = [
            Question(
                quiz=quiz,
                order=q.get('order', idx + 1),
                question_type=q.get('question_type', 'mcq'),
                text=q['text'],
                explanation=q.get('explanation', ''),
                points=q.get('points', 1),
                options=q.get('options', []),
                correct_answer=q.get('correct_answer', []),
            )
            for idx, q in enumerate(questions_data)
        ]
        Question.objects.bulk_create(questions)

        quiz.status = Quiz.Status.PUBLISHED
        quiz.question_count = len(questions)
        quiz.save(update_fields=['status', 'question_count'])

        logger.info('Quiz %s created with %d questions by %s', quiz.id, len(questions), request.user)
        return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_201_CREATED)


class QuizUpdateView(generics.UpdateAPIView):
    """PATCH /api/v1/quizzes/<id>/edit/ — owner or admin only."""
    serializer_class = QuizUpdateSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    lookup_field = 'id'
    http_method_names = ['patch']

    def get_queryset(self):
        return Quiz.objects.all()

    def get_object(self):
        quiz = get_object_or_404(Quiz, id=self.kwargs['id'])
        self.check_object_permissions(self.request, quiz)
        return quiz


class QuizDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/quizzes/<id>/delete/ — soft-deletes by archiving."""
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    lookup_field = 'id'

    def get_queryset(self):
        return Quiz.objects.all()

    def get_object(self):
        quiz = get_object_or_404(Quiz, id=self.kwargs['id'])
        self.check_object_permissions(self.request, quiz)
        return quiz

    def destroy(self, request, *args, **kwargs):
        quiz = self.get_object()
        quiz.status = Quiz.Status.ARCHIVED
        quiz.save(update_fields=['status'])
        return Response({'message': 'Quiz archived successfully.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AIGenerationThrottle])
def regenerate_quiz(request, id):
    """
    POST /api/v1/quizzes/<id>/regenerate/
    Re-run AI generation for an existing quiz (owner/admin only).
    """
    quiz = get_object_or_404(Quiz, id=id)

    if quiz.creator != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        return Response(
            {'error': {'code': 'forbidden', 'message': 'Not authorised.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        questions_data = generate_quiz_questions(
            topic=quiz.topic,
            count=quiz.question_count,
            difficulty=quiz.difficulty,
            use_cache=False,
        )
    except AIServiceError as exc:
        return Response(
            {'error': {'code': 'ai_generation_failed', 'message': str(exc)}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    with transaction.atomic():
        quiz.questions.all().delete()
        new_questions = [
            Question(
                quiz=quiz,
                order=i + 1,
                question_type=q.get('question_type', 'mcq'),
                text=q['text'],
                explanation=q.get('explanation', ''),
                points=q.get('points', 1),
                options=q.get('options', []),
                correct_answer=q.get('correct_answer', []),
            )
            for i, q in enumerate(questions_data)
        ]
        Question.objects.bulk_create(new_questions)
        quiz.status = Quiz.Status.PUBLISHED
        quiz.question_count = len(new_questions)
        quiz.generation_error = ''
        quiz.save(update_fields=['status', 'question_count', 'generation_error'])

    logger.info('Quiz %s regenerated with %d questions', quiz.id, len(new_questions))
    return Response(QuizDetailSerializer(quiz).data)
