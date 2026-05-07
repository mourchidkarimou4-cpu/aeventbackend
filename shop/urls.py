from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, OrderViewSet, AddonViewSet, CodePromoViewSet, validate_promo, ZoneLivraisonViewSet, BonCadeauViewSet, FideliteViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('products',   ProductViewSet)
router.register('orders',     OrderViewSet)
router.register('addons',     AddonViewSet)
router.register('promos',     CodePromoViewSet)
router.register('livraison',  ZoneLivraisonViewSet)
router.register('bons-cadeaux', BonCadeauViewSet)
router.register('fidelite',    FideliteViewSet)

urlpatterns = [path('', include(router.urls))]
