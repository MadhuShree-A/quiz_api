from django.urls import path
from apps.users.views.auth_views import register, login, logout, token_refresh

urlpatterns = [
    path('register/', register, name='auth-register'),
    path('login/', login, name='auth-login'),
    path('logout/', logout, name='auth-logout'),
    path('token/refresh/', token_refresh, name='auth-token-refresh'),
]
