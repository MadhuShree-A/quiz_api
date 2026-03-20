from django.contrib import admin
from .models import Quiz, Question, QuizAttempt, UserAnswer


class QuestionInline(admin.TabularInline):
    model = Question
    fields = ['order', 'question_type', 'text', 'points']
    readonly_fields = ['order']
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'difficulty', 'status', 'question_count',
                    'attempt_count', 'avg_score', 'creator', 'created_at']
    list_filter = ['status', 'difficulty', 'is_public']
    search_fields = ['title', 'topic', 'creator__email']
    readonly_fields = ['attempt_count', 'avg_score', 'ai_model_used', 'created_at', 'updated_at']
    inlines = [QuestionInline]
    ordering = ['-created_at']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'status', 'score_percentage', 'started_at', 'completed_at']
    list_filter = ['status', 'difficulty_at_attempt']
    search_fields = ['user__email', 'quiz__title']
    readonly_fields = ['started_at', 'completed_at', 'time_taken_seconds']
    ordering = ['-started_at']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['quiz', 'order', 'question_type', 'text_preview', 'points']
    list_filter = ['question_type']
    search_fields = ['quiz__title', 'text']

    def text_preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    text_preview.short_description = 'Text'
