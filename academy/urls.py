from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormationViewSet, ReservationViewSet

router = DefaultRouter()
router.register('formations',   FormationViewSet)
router.register('reservations', ReservationViewSet)

urlpatterns = [path('', include(router.urls))]
