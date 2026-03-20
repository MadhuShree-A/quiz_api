"""
Usage:
    python manage.py snapshot_analytics
    python manage.py snapshot_analytics --date 2024-03-15

Run daily via cron or a scheduler (e.g. Heroku Scheduler).
"""
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import date as date_type

from apps.quizzes.models import Quiz, QuizAttempt
from apps.analytics.models import QuizAnalyticsSnapshot, QuestionAnalytics


class Command(BaseCommand):
    help = 'Generate daily analytics snapshots for all published quizzes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to snapshot (YYYY-MM-DD). Defaults to today.',
        )

    def handle(self, *args, **options):
        raw_date = options.get('date')
        if raw_date:
            snapshot_date = date_type.fromisoformat(raw_date)
        else:
            snapshot_date = timezone.now().date()

        self.stdout.write(f'Snapshotting analytics for {snapshot_date}...')

        quizzes = Quiz.objects.filter(status=Quiz.Status.PUBLISHED)
        created = updated = 0

        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(
                quiz=quiz,
                started_at__date=snapshot_date,
            )
            completed = attempts.filter(status=QuizAttempt.Status.COMPLETED)
            agg = completed.aggregate(
                avg_score=Avg('score_percentage'),
                avg_time=Avg('time_taken_seconds'),
                passed=Count('id', filter=Q(score_percentage__gte=getattr(quiz, 'pass_percentage', 60))),
            )

            total_completed = completed.count()
            pass_rate = (
                round((agg['passed'] or 0) / total_completed * 100, 2)
                if total_completed else 0.0
            )

            snap, was_created = QuizAnalyticsSnapshot.objects.update_or_create(
                quiz=quiz,
                date=snapshot_date,
                defaults={
                    'total_attempts': attempts.count(),
                    'completed_attempts': total_completed,
                    'average_score': round(agg['avg_score'] or 0, 2),
                    'pass_rate': pass_rate,
                    'avg_time_seconds': round(agg['avg_time'] or 0, 1),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Update per-question analytics
        self._update_question_analytics()

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {created} snapshots, updated {updated}. '
                f'Question analytics refreshed.'
            )
        )

    def _update_question_analytics(self):
        from apps.quizzes.models import Question, UserAnswer
        from django.db.models import Avg as DjAvg, Count as DjCount

        questions = Question.objects.prefetch_related('user_answers').all()
        for question in questions:
            answers = question.user_answers.all()
            total = answers.count()
            if not total:
                continue

            correct = answers.filter(is_correct=True).count()
            avg_time_agg = answers.aggregate(avg=DjAvg('time_taken_seconds'))
            avg_time = round(avg_time_agg['avg'] or 0, 1)

            # Build option distribution
            dist: dict = {}
            for ans in answers.values_list('selected_answer', flat=True):
                if isinstance(ans, list):
                    for opt in ans:
                        dist[str(opt)] = dist.get(str(opt), 0) + 1
                elif ans is not None:
                    dist[str(ans)] = dist.get(str(ans), 0) + 1

            QuestionAnalytics.objects.update_or_create(
                question=question,
                defaults={
                    'total_answers': total,
                    'correct_answers': correct,
                    'avg_time_seconds': avg_time,
                    'option_distribution': dist,
                },
            )
