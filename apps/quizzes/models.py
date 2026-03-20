import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Quiz(models.Model):
    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        GENERATING = 'generating', 'Generating'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_quizzes',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    topic = models.CharField(max_length=100, db_index=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    question_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    time_limit_minutes = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='0 or null means no time limit',
    )
    is_public = models.BooleanField(default=True)
    allow_retake = models.BooleanField(default=True)  # ← add this line
    pass_percentage = models.FloatField(default=60.0)  # ← add this too
    tags = models.JSONField(default=list, blank=True)

    # AI generation metadata
    ai_model_used = models.CharField(max_length=100, blank=True)
    ai_prompt_used = models.TextField(blank=True)
    generation_error = models.TextField(blank=True)

    # Stats (denormalised for performance)
    attempt_count = models.PositiveIntegerField(default=0)
    avg_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic', 'difficulty', 'status']),
            models.Index(fields=['is_public', 'status']),
            models.Index(fields=['creator', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.difficulty})'

    @property
    def is_ready(self):
        return self.status == self.Status.PUBLISHED

    def update_stats(self):
        """Recalculate attempt_count and avg_score from attempts table."""
        from django.db.models import Avg, Count
        stats = self.attempts.filter(
            status=QuizAttempt.Status.COMPLETED
        ).aggregate(count=Count('id'), avg=Avg('score_percentage'))
        self.attempt_count = stats['count'] or 0
        self.avg_score = round(stats['avg'] or 0.0, 2)
        self.save(update_fields=['attempt_count', 'avg_score'])


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'mcq', 'Multiple Choice'
        TRUE_FALSE = 'tf', 'True / False'
        SHORT_ANSWER = 'short', 'Short Answer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(
        max_length=10, choices=QuestionType.choices, default=QuestionType.MULTIPLE_CHOICE
    )
    order = models.PositiveSmallIntegerField(default=0)
    text = models.TextField()
    explanation = models.TextField(blank=True, help_text='Shown after answering')
    points = models.PositiveSmallIntegerField(default=1)

    # For MCQ: list of {"id": "a", "text": "..."} dicts; for T/F: [{"id":"true",...},...]
    options = models.JSONField(default=list)
    # Correct answer(s): list of option ids for MCQ/TF, or string for short answer
    correct_answer = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'questions'
        ordering = ['quiz', 'order']
        unique_together = [('quiz', 'order')]
        indexes = [models.Index(fields=['quiz', 'order'])]

    def __str__(self):
        return f'Q{self.order}: {self.text[:60]}'

    def check_answer(self, user_answer) -> bool:
        """Return True if the provided answer is correct."""
        correct = self.correct_answer
        if self.question_type == self.QuestionType.SHORT_ANSWER:
            # Case-insensitive partial match
            if isinstance(correct, list):
                return any(str(a).lower() in str(user_answer).lower() for a in correct)
            return str(correct).lower() in str(user_answer).lower()
        # MCQ / T-F: compare sorted lists of selected option ids
        if isinstance(user_answer, str):
            user_answer = [user_answer]
        if isinstance(correct, str):
            correct = [correct]
        return sorted(user_answer) == sorted(correct)


class QuizAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        TIMED_OUT = 'timed_out', 'Timed Out'
        ABANDONED = 'abandoned', 'Abandoned'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Scoring
    total_questions = models.PositiveSmallIntegerField(default=0)
    correct_answers = models.PositiveSmallIntegerField(default=0)
    total_points_earned = models.PositiveSmallIntegerField(default=0)
    total_points_possible = models.PositiveSmallIntegerField(default=0)
    score_percentage = models.FloatField(default=0.0)

    # Snapshot of quiz difficulty at time of attempt
    difficulty_at_attempt = models.CharField(max_length=10, blank=True)

    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['quiz', 'status']),
            models.Index(fields=['user', 'quiz']),
        ]

    def __str__(self):
        return f'{self.user.username} → {self.quiz.title} ({self.status})'

    @property
    def is_timed_out(self):
        if self.status != self.Status.IN_PROGRESS:
            return False
        if not self.quiz.time_limit_minutes:
            return False
        elapsed = (timezone.now() - self.started_at).total_seconds() / 60
        return elapsed > self.quiz.time_limit_minutes

    def complete(self):
        """Finalise scoring and mark as completed."""
        answers = self.answers.select_related('question').all()
        correct = sum(1 for a in answers if a.is_correct)
        earned = sum(a.question.points for a in answers if a.is_correct)
        possible = sum(q.points for q in self.quiz.questions.all())

        self.correct_answers = correct
        self.total_questions = self.quiz.question_count
        self.total_points_earned = earned
        self.total_points_possible = possible
        self.score_percentage = round(earned / possible * 100, 2) if possible else 0.0
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.time_taken_seconds = int((self.completed_at - self.started_at).total_seconds())
        self.difficulty_at_attempt = self.quiz.difficulty
        self.save()

        # Update quiz stats
        self.quiz.update_stats()
        # Update user profile stats
        self._update_user_profile()

    def _update_user_profile(self):
        from apps.users.models import UserProfile
        from django.db.models import F
        import datetime
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        today = timezone.now().date()
        streak_days = profile.streak_days
        if profile.last_activity_date == today - datetime.timedelta(days=1):
            streak_days += 1
        elif profile.last_activity_date != today:
            streak_days = 1

        UserProfile.objects.filter(user=self.user).update(
            total_quizzes_taken=F('total_quizzes_taken') + 1,
            total_questions_answered=F('total_questions_answered') + self.total_questions,
            total_correct_answers=F('total_correct_answers') + self.correct_answers,
            total_points=F('total_points') + self.total_points_earned,
            streak_days=streak_days,
            last_activity_date=today,
        )


class UserAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers')

    # What the user submitted: list of option ids or string
    selected_answer = models.JSONField()
    is_correct = models.BooleanField(default=False)
    points_earned = models.PositiveSmallIntegerField(default=0)
    time_taken_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_answers'
        unique_together = [('attempt', 'question')]
        indexes = [models.Index(fields=['attempt', 'question'])]

    def save(self, *args, **kwargs):
        self.is_correct = self.question.check_answer(self.selected_answer)
        self.points_earned = self.question.points if self.is_correct else 0
        super().save(*args, **kwargs)
