from rest_framework import serializers
from .models import QuizAnalyticsSnapshot, UserAnalyticsSummary, QuestionAnalytics


class QuizAnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnalyticsSnapshot
        fields = [
            'date', 'total_attempts', 'completed_attempts',
            'average_score', 'pass_rate', 'avg_time_seconds',
        ]


class QuizAnalyticsSummarySerializer(serializers.Serializer):
    """Aggregated overview for a quiz's lifetime performance."""
    quiz_id = serializers.UUIDField()
    quiz_title = serializers.CharField()
    total_attempts = serializers.IntegerField()
    completed_attempts = serializers.IntegerField()
    average_score = serializers.FloatField()
    pass_rate = serializers.FloatField()
    avg_time_seconds = serializers.FloatField()
    score_distribution = serializers.DictField()     # {"0-20": N, "21-40": N, ...}
    daily_trend = QuizAnalyticsSnapshotSerializer(many=True)


class UserAnalyticsSummarySerializer(serializers.ModelSerializer):
    accuracy_percentage = serializers.ReadOnlyField()

    class Meta:
        model = UserAnalyticsSummary
        fields = [
            'period', 'period_start',
            'quizzes_taken', 'questions_answered', 'correct_answers',
            'average_score', 'accuracy_percentage', 'total_time_seconds',
            'difficulty_breakdown', 'topic_breakdown',
        ]


class QuestionAnalyticsSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    difficulty_rating = serializers.ReadOnlyField()

    class Meta:
        model = QuestionAnalytics
        fields = [
            'question', 'question_text',
            'total_answers', 'correct_answers',
            'avg_time_seconds', 'option_distribution', 'difficulty_rating',
            'updated_at',
        ]


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    username = serializers.CharField()
    avatar_url = serializers.CharField()
    total_points = serializers.IntegerField()
    total_quizzes_taken = serializers.IntegerField()
    accuracy_percentage = serializers.FloatField()
    streak_days = serializers.IntegerField()


class UserDashboardSerializer(serializers.Serializer):
    """All-in-one payload for a user's personal dashboard."""
    profile = serializers.DictField()
    recent_attempts = serializers.ListField()
    performance_by_difficulty = serializers.DictField()
    performance_by_topic = serializers.DictField()
    weekly_activity = serializers.ListField()   # last 7 days attempt counts
    achievements = serializers.ListField()
