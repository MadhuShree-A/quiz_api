from django.urls import path
from apps.users.views.user_views import (
    MeView, change_password, UserPreferencesView, PublicUserView,
    AdminUserListView, AdminUserDetailView,
)

urlpatterns = [
    path('', AdminUserListView.as_view(), name='admin-user-list'),
    path('me/', MeView.as_view(), name='user-me'),
    path('me/change-password/', change_password, name='user-change-password'),
    path('me/preferences/', UserPreferencesView.as_view(), name='user-preferences'),
    path('<str:username>/profile/', PublicUserView.as_view(), name='user-public-profile'),
    path('<uuid:id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
]
