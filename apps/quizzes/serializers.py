from rest_framework import serializers
from django.conf import settings
from .models import Quiz, Question, QuizAttempt, UserAnswer


# ─── Question ──────────────────────────────────────────────────────────────────

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'order', 'question_type', 'text', 'options',
            'points', 'explanation',
        ]
        # NOTE: correct_answer is intentionally excluded here (shown only in results)


class QuestionWithAnswerSerializer(QuestionSerializer):
    """Includes correct answer — used in results/review views."""
    class Meta(QuestionSerializer.Meta):
        fields = QuestionSerializer.Meta.fields + ['correct_answer']


# ─── Quiz ──────────────────────────────────────────────────────────────────────

class QuizListSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'topic', 'difficulty', 'status',
            'question_count', 'time_limit_minutes', 'is_public',
            'tags', 'attempt_count', 'avg_score',
            'creator_username', 'created_at',
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    creator_username = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'topic', 'difficulty', 'status',
            'question_count', 'time_limit_minutes', 'is_public', 'tags',
            'attempt_count', 'avg_score', 'ai_model_used',
            'creator_username', 'created_at', 'updated_at', 'questions',
        ]


class QuizCreateSerializer(serializers.ModelSerializer):
    question_types = serializers.ListField(
        child=serializers.ChoiceField(choices=['mcq', 'tf', 'short']),
        default=['mcq'],
        write_only=True,
    )
    additional_context = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Quiz
        fields = [
            'title', 'description', 'topic', 'difficulty',
            'question_count', 'time_limit_minutes', 'is_public', 'tags',
            'question_types', 'additional_context',
        ]

    def validate_question_count(self, value):
        if value < settings.QUIZ_MIN_QUESTIONS or value > settings.QUIZ_MAX_QUESTIONS:
            raise serializers.ValidationError(
                f'question_count must be between {settings.QUIZ_MIN_QUESTIONS} '
                f'and {settings.QUIZ_MAX_QUESTIONS}.'
            )
        return value

    def validate_topic(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError('Topic must be at least 3 characters.')
        return value.strip()


class QuizUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'time_limit_minutes', 'is_public', 'tags', 'status']

    def validate_status(self, value):
        allowed_transitions = {
            Quiz.Status.DRAFT: [Quiz.Status.PUBLISHED, Quiz.Status.ARCHIVED],
            Quiz.Status.PUBLISHED: [Quiz.Status.ARCHIVED],
            Quiz.Status.ARCHIVED: [Quiz.Status.PUBLISHED],
            Quiz.Status.FAILED: [Quiz.Status.DRAFT],
        }
        current = self.instance.status if self.instance else None
        if current and value not in allowed_transitions.get(current, [value]):
            raise serializers.ValidationError(
                f'Cannot transition from {current} to {value}.'
            )
        return value


# ─── Attempt ───────────────────────────────────────────────────────────────────

class StartAttemptSerializer(serializers.Serializer):
    """No body required — quiz_id comes from the URL."""
    pass


class UserAnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    selected_answer = serializers.JSONField()
    time_taken_seconds = serializers.IntegerField(required=False, min_value=0)


class BulkAnswerSubmitSerializer(serializers.Serializer):
    """Submit all answers at once for a completed attempt."""
    answers = UserAnswerSubmitSerializer(many=True)


class UserAnswerResultSerializer(serializers.ModelSerializer):
    question = QuestionWithAnswerSerializer(read_only=True)

    class Meta:
        model = UserAnswer
        fields = [
            'id', 'question', 'selected_answer', 'is_correct',
            'points_earned', 'time_taken_seconds',
        ]


class AttemptListSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_topic = serializers.CharField(source='quiz.topic', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'quiz_topic', 'status',
            'score_percentage', 'correct_answers', 'total_questions',
            'time_taken_seconds', 'started_at', 'completed_at',
        ]


class AttemptDetailSerializer(serializers.ModelSerializer):
    answers = UserAnswerResultSerializer(many=True, read_only=True)
    quiz = QuizListSerializer(read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'status',
            'score_percentage', 'correct_answers', 'total_questions',
            'total_points_earned', 'total_points_possible',
            'time_taken_seconds', 'started_at', 'completed_at',
            'difficulty_at_attempt', 'answers',
        ]
