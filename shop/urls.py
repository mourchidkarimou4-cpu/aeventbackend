from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, OrderViewSet, AddonViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('products',   ProductViewSet)
router.register('orders',     OrderViewSet)
router.register('addons',     AddonViewSet)

urlpatterns = [path('', include(router.urls))]
