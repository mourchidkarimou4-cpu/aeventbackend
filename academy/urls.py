from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormationPresentiellViewSet, DossierCandidatureViewSet, FormationViewSet, ReservationViewSet

router = DefaultRouter()
router.register('formations',   FormationViewSet)
router.register('reservations', ReservationViewSet)

router.register('formations-presentiel', FormationPresentiellViewSet)
router.register('candidatures', DossierCandidatureViewSet)
urlpatterns = [path('', include(router.urls))]
