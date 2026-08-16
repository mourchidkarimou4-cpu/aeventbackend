from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormationPresentiellViewSet, DossierCandidatureViewSet, FormationViewSet, ReservationViewSet
from core.views import DossierUploadView

router = DefaultRouter()
router.register('formations',   FormationViewSet)
router.register('reservations', ReservationViewSet)

router.register('formations-presentiel', FormationPresentiellViewSet)
router.register('candidatures', DossierCandidatureViewSet)
urlpatterns = [
    path('dossier-upload/', DossierUploadView.as_view()),
    path('', include(router.urls)),
]
