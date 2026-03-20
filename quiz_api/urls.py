from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from quiz_api.docs import api_docs

urlpatterns = [
    path('', RedirectView.as_view(url='/docs/', permanent=False)),
    path('admin/', admin.site.urls),
    path('docs', api_docs, name='api-docs'),
    path('docs/', api_docs, name='api-docs-slash'),
    path('api/v1/auth/', include('apps.users.urls.auth_urls')),
    path('api/v1/users/', include('apps.users.urls.user_urls')),
    path('api/v1/quizzes/', include('apps.quizzes.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'quiz_api.exceptions.handler_404'
handler500 = 'quiz_api.exceptions.handler_500'