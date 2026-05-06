from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteSettingsView, GaleriePhotoViewSet, ChangePasswordView, NewsletterView, NewsletterListView, AvisView, AvisAdminView, TemoignageViewSet
from .stats import DashboardStatsView

router = DefaultRouter()
router.register('galerie', GaleriePhotoViewSet)
router.register('temoignages', TemoignageViewSet)

urlpatterns = [
    path('settings/',        SiteSettingsView.as_view()),
    path('dashboard/stats/', DashboardStatsView.as_view()),
    path('', include(router.urls)),
]
