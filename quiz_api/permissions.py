from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminUser(BasePermission):
    """Only users with role='admin' or is_staff=True."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'admin' or request.user.is_staff)
        )


class IsEducatorOrAdmin(BasePermission):
    """Educators and admins — can create/manage quizzes."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ('educator', 'admin') or request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    """Object-level: only the creator or an admin can modify."""
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.role == 'admin':
            return True
        # obj may be a Quiz or QuizAttempt — handle both
        owner = getattr(obj, 'creator', None) or getattr(obj, 'user', None)
        return owner == request.user


class IsOwnerOrReadOnly(BasePermission):
    """Safe methods are open; writes require ownership or admin."""
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff or request.user.role == 'admin':
            return True
        owner = getattr(obj, 'creator', None) or getattr(obj, 'user', None)
        return owner == request.user
