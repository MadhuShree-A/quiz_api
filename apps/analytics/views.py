import logging
from collections import defaultdict
from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from apps.quizzes.models import Quiz, QuizAttempt
from apps.users.models import UserProfile
from .models import QuizAnalyticsSnapshot, UserAnalyticsSummary, QuestionAnalytics
from .serializers import (
    QuizAnalyticsSummarySerializer, UserAnalyticsSummarySerializer,
    LeaderboardEntrySerializer, UserDashboardSerializer,
    QuestionAnalyticsSerializer,
)
from quiz_api.permissions import IsOwnerOrAdmin, IsAdminUser

logger = logging.getLogger(__name__)

CACHE_TTL_SHORT = 60 * 5    # 5 minutes
CACHE_TTL_LONG = 60 * 60    # 1 hour


# ─── User dashboard ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_dashboard(request):
    """
    GET /api/v1/analytics/dashboard/
    All-in-one payload for the current user's personal dashboard.
    Cached per user for 5 minutes.
    """
    user = request.user
    cache_key = f'dashboard:{user.id}'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Recent attempts (last 10)
    recent_attempts = (
        QuizAttempt.objects
        .filter(user=user, status=QuizAttempt.Status.COMPLETED)
        .select_related('quiz')
        .order_by('-completed_at')[:10]
    )

    # Performance by difficulty
    difficulty_stats = (
        QuizAttempt.objects
        .filter(user=user, status=QuizAttempt.Status.COMPLETED)
        .values('difficulty_at_attempt')
        .annotate(
            count=Count('id'),
            avg_score=Avg('score_percentage'),
            total_correct=Sum('correct_answers'),
            total_questions=Sum('total_questions'),
        )
    )
    perf_by_difficulty = {
        row['difficulty_at_attempt']: {
            'attempts': row['count'],
            'avg_score': round(row['avg_score'] or 0, 2),
            'accuracy': round(
                (row['total_correct'] or 0) / (row['total_questions'] or 1) * 100, 2
            ),
        }
        for row in difficulty_stats
    }

    # Performance by topic (top 8)
    topic_stats = (
        QuizAttempt.objects
        .filter(user=user, status=QuizAttempt.Status.COMPLETED)
        .values('quiz__topic')
        .annotate(count=Count('id'), avg_score=Avg('score_percentage'))
        .order_by('-count')[:8]
    )
    perf_by_topic = {
        row['quiz__topic']: {
            'attempts': row['count'],
            'avg_score': round(row['avg_score'] or 0, 2),
        }
        for row in topic_stats
    }

    # Weekly activity (last 7 days — attempt count per day)
    today = timezone.now().date()
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = QuizAttempt.objects.filter(
            user=user,
            started_at__date=day,
        ).count()
        weekly.append({'date': day.isoformat(), 'attempts': count})

    # Simple achievements
    achievements = _compute_achievements(profile)

    payload = {
        'profile': {
            'username': user.username,
            'full_name': user.full_name,
            'avatar_url': user.avatar_url,
            'total_quizzes_taken': profile.total_quizzes_taken,
            'total_points': profile.total_points,
            'accuracy_percentage': profile.accuracy_percentage,
            'streak_days': profile.streak_days,
        },
        'recent_attempts': [
            {
                'id': str(a.id),
                'quiz_title': a.quiz.title,
                'quiz_topic': a.quiz.topic,
                'score_percentage': a.score_percentage,
                'completed_at': a.completed_at,
                'passed': a.score_percentage >= (a.quiz.pass_percentage
                                                  if hasattr(a.quiz, 'pass_percentage') else 60),
            }
            for a in recent_attempts
        ],
        'performance_by_difficulty': perf_by_difficulty,
        'performance_by_topic': perf_by_topic,
        'weekly_activity': weekly,
        'achievements': achievements,
    }

    cache.set(cache_key, payload, timeout=CACHE_TTL_SHORT)
    return Response(payload)


def _compute_achievements(profile: UserProfile) -> list[dict]:
    achievements = []
    milestones = [
        (1, 'first_quiz', '🎯', 'First Quiz', 'Completed your first quiz!'),
        (10, 'quiz_ten', '🔥', 'On Fire', 'Completed 10 quizzes'),
        (50, 'quiz_fifty', '⚡', 'Quiz Machine', 'Completed 50 quizzes'),
        (100, 'quiz_hundred', '🏆', 'Century Club', 'Completed 100 quizzes'),
    ]
    for threshold, key, icon, name, desc in milestones:
        if profile.total_quizzes_taken >= threshold:
            achievements.append({'id': key, 'icon': icon, 'name': name, 'description': desc})
    if profile.streak_days >= 7:
        achievements.append({
            'id': 'week_streak', 'icon': '📅', 'name': 'Week Warrior',
            'description': f'{profile.streak_days}-day streak!'
        })
    if profile.accuracy_percentage >= 90 and profile.total_quizzes_taken >= 5:
        achievements.append({
            'id': 'sharp_mind', 'icon': '🧠', 'name': 'Sharp Mind',
            'description': '90%+ accuracy across 5+ quizzes'
        })
    return achievements


# ─── Quiz analytics ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quiz_analytics(request, quiz_id):
    """
    GET /api/v1/analytics/quizzes/<quiz_id>/
    Detailed stats for a quiz. Only the creator or admin can access.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.creator != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        return Response(
            {'error': {'code': 'forbidden', 'message': 'Not authorised.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    cache_key = f'quiz_analytics:{quiz_id}'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    completed = QuizAttempt.objects.filter(quiz=quiz, status=QuizAttempt.Status.COMPLETED)

    # Score distribution buckets
    buckets = defaultdict(int)
    labels = ['0-20', '21-40', '41-60', '61-80', '81-100']
    for score in completed.values_list('score_percentage', flat=True):
        bucket_idx = min(int(score // 20), 4)
        buckets[labels[bucket_idx]] += 1
    score_distribution = {label: buckets[label] for label in labels}

    agg = completed.aggregate(
        total=Count('id'),
        avg_score=Avg('score_percentage'),
        avg_time=Avg('time_taken_seconds'),
        passed=Count('id', filter=Q(score_percentage__gte=getattr(quiz, 'pass_percentage', 60))),
    )

    total = agg['total'] or 0
    passed = agg['passed'] or 0

    # Daily trend (last 30 days from snapshots or live)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    snapshots = QuizAnalyticsSnapshot.objects.filter(quiz=quiz, date__gte=thirty_days_ago)

    payload = {
        'quiz_id': str(quiz.id),
        'quiz_title': quiz.title,
        'total_attempts': QuizAttempt.objects.filter(quiz=quiz).count(),
        'completed_attempts': total,
        'average_score': round(agg['avg_score'] or 0, 2),
        'pass_rate': round(passed / total * 100, 2) if total else 0.0,
        'avg_time_seconds': round(agg['avg_time'] or 0, 1),
        'score_distribution': score_distribution,
        'daily_trend': [
            {
                'date': s.date.isoformat(),
                'total_attempts': s.total_attempts,
                'average_score': s.average_score,
                'pass_rate': s.pass_rate,
            }
            for s in snapshots
        ],
    }

    cache.set(cache_key, payload, timeout=CACHE_TTL_SHORT)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quiz_question_analytics(request, quiz_id):
    """
    GET /api/v1/analytics/quizzes/<quiz_id>/questions/
    Per-question difficulty stats for a quiz (creator/admin only).
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.creator != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        return Response(
            {'error': {'code': 'forbidden', 'message': 'Not authorised.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    question_analytics = (
        QuestionAnalytics.objects
        .filter(question__quiz=quiz)
        .select_related('question')
        .order_by('question__order')
    )
    return Response(QuestionAnalyticsSerializer(question_analytics, many=True).data)


# ─── Leaderboard ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaderboard(request):
    """
    GET /api/v1/analytics/leaderboard/
    Top 50 users by total_points.
    Cached for 1 hour.
    Query params:
      ?quiz=<uuid>  — leaderboard for a specific quiz
      ?period=weekly|monthly|all_time  (default: all_time)
    """
    quiz_id = request.query_params.get('quiz')
    period = request.query_params.get('period', 'all_time')

    cache_key = f'leaderboard:{quiz_id or "global"}:{period}'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    if quiz_id:
        # Quiz-specific leaderboard
        entries = (
            QuizAttempt.objects
            .filter(quiz_id=quiz_id, status=QuizAttempt.Status.COMPLETED)
            .values('user__username', 'user__avatar_url')
            .annotate(
                best_score=Avg('score_percentage'),
                attempts=Count('id'),
            )
            .order_by('-best_score')[:50]
        )
        data = [
            {
                'rank': i + 1,
                'username': e['user__username'],
                'avatar_url': e['user__avatar_url'] or '',
                'best_score': round(e['best_score'], 2),
                'attempts': e['attempts'],
            }
            for i, e in enumerate(entries)
        ]
    else:
        # Global leaderboard from UserProfile
        profiles = (
            UserProfile.objects
            .select_related('user')
            .filter(user__is_active=True)
            .order_by('-total_points')[:50]
        )
        data = [
            {
                'rank': i + 1,
                'username': p.user.username,
                'avatar_url': p.user.avatar_url or '',
                'total_points': p.total_points,
                'total_quizzes_taken': p.total_quizzes_taken,
                'accuracy_percentage': p.accuracy_percentage,
                'streak_days': p.streak_days,
            }
            for i, p in enumerate(profiles)
        ]

    cache.set(cache_key, data, timeout=CACHE_TTL_LONG)
    return Response(data)


# ─── Admin overview ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_overview(request):
    """
    GET /api/v1/analytics/admin/overview/
    Platform-wide stats for admins.
    """
    from apps.users.models import User

    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    user_count = User.objects.filter(is_active=True).count()
    quiz_count = Quiz.objects.filter(status=Quiz.Status.PUBLISHED).count()
    attempt_count = QuizAttempt.objects.filter(status=QuizAttempt.Status.COMPLETED).count()
    new_users_30d = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()
    new_attempts_30d = QuizAttempt.objects.filter(
        started_at__date__gte=thirty_days_ago
    ).count()

    avg_score = QuizAttempt.objects.filter(
        status=QuizAttempt.Status.COMPLETED
    ).aggregate(avg=Avg('score_percentage'))['avg'] or 0

    return Response({
        'total_users': user_count,
        'total_published_quizzes': quiz_count,
        'total_completed_attempts': attempt_count,
        'new_users_last_30_days': new_users_30d,
        'new_attempts_last_30_days': new_attempts_30d,
        'platform_average_score': round(avg_score, 2),
    })
