"""
admin.py — registers all models with Django's built-in admin.
Access at /admin/ with a superuser account.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'role', 'is_active', 'email_verified', 'date_joined']
    list_filter = ['role', 'is_active', 'email_verified', 'is_staff']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Quiz App', {'fields': ('role', 'bio', 'avatar_url', 'email_verified')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Quiz App', {'fields': ('email', 'role')}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_quizzes_taken', 'total_points', 'accuracy_percentage', 'streak_days']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['accuracy_percentage']
