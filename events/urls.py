from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuoteRequestViewSet, PrintFileUploadView

router = DefaultRouter()
router.register('quotes',       QuoteRequestViewSet)
router.register('upload-files', PrintFileUploadView, basename='printfile-upload')

urlpatterns = [path('', include(router.urls))]
