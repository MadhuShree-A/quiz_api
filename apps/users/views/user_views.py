from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from ..models import User, UserProfile
from ..serializers import (
    UserSerializer, UserUpdateSerializer, ChangePasswordSerializer,
    UserPreferencesSerializer, AdminUserSerializer,
)
from quiz_api.permissions import IsAdminUser


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/users/me/ — current user's own profile."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(instance).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST /api/v1/users/me/change-password/"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data['new_password'])
    request.user.save(update_fields=['password'])
    return Response({'message': 'Password changed successfully.'})


class UserPreferencesView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/users/me/preferences/"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserPreferencesSerializer

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class PublicUserView(generics.RetrieveAPIView):
    """GET /api/v1/users/<username>/ — public profile."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    lookup_field = 'username'
    queryset = User.objects.filter(is_active=True).select_related('profile')


# ─── Admin views ───────────────────────────────────────────────────────────────

class AdminUserListView(generics.ListAPIView):
    """GET /api/v1/users/ — admin only."""
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('profile').order_by('-date_joined')
    search_fields = ['email', 'username', 'first_name', 'last_name']
    filterset_fields = ['role', 'is_active', 'email_verified']
    ordering_fields = ['date_joined', 'username', 'email']


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/users/<id>/ — admin only."""
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('profile')
    lookup_field = 'id'

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False  # Soft delete
        user.save(update_fields=['is_active'])
        return Response({'message': 'User deactivated.'}, status=status.HTTP_200_OK)
