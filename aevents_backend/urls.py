from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "A'Events Bénin — Administration"
admin.site.site_title = "A'Events Admin"
admin.site.index_title = "Tableau de bord"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/',    include('core.urls')),
    path('api/shop/',    include('shop.urls')),
    path('api/events/',  include('events.urls')),
    path('api/academy/', include('academy.urls')),
    path('api/chat/', include('chat.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# JWT
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
urlpatterns += [
    path('api/auth/token/',         TokenObtainPairView.as_view()),
    path('api/auth/token/refresh/', TokenRefreshView.as_view()),
]
