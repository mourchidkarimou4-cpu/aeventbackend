from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteSettingsView, GaleriePhotoViewSet, ChangePasswordView, NewsletterView, NewsletterListView, AvisView, AvisAdminView, TemoignageViewSet, AdminUsersView, AuthMeView
from .stats import DashboardStatsView

router = DefaultRouter()
router.register('galerie', GaleriePhotoViewSet)
router.register('temoignages', TemoignageViewSet)

urlpatterns = [
    path('settings/',        SiteSettingsView.as_view()),
    path('dashboard/stats/', DashboardStatsView.as_view()),
    path('avis/',            AvisView.as_view()),
    path('avis/admin/',      AvisAdminView.as_view()),
    path('auth/me/', AuthMeView.as_view()),
    path('', include(router.urls)),
    path('newsletter/', NewsletterView.as_view()),
    path('newsletter/list/', NewsletterListView.as_view()),
]
