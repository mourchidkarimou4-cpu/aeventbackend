from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PackViewSet, CategoryViewSet, ProductViewSet, OrderViewSet, AddonViewSet, CodePromoViewSet, ValidatePromoView, ZoneLivraisonViewSet, BonCadeauViewSet, FideliteViewSet, ParrainageViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('products',   ProductViewSet)
router.register('orders',     OrderViewSet)
router.register('addons',     AddonViewSet)
router.register('promos',     CodePromoViewSet)
router.register('livraison',  ZoneLivraisonViewSet)
router.register('bons-cadeaux', BonCadeauViewSet)
router.register('fidelite',    FideliteViewSet)
router.register('parrainages', ParrainageViewSet)
router.register('packs', PackViewSet)

urlpatterns = [
    path('promos/validate/', ValidatePromoView.as_view()),
    path('', include(router.urls)),
]
