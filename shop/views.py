from rest_framework import viewsets, permissions, status, filters, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product, Order
from .serializers import (
    CategorySerializer, ProductSerializer, ProductListSerializer,
    OrderCreateSerializer, OrderReadSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('order')
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


from .models import Addon
from .serializers import AddonSerializer

class AddonViewSet(viewsets.ModelViewSet):
    queryset = Addon.objects.all().order_by('name')
    serializer_class = AddonSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().select_related('category').prefetch_related('available_addons')
    lookup_field = 'pk'
    permission_classes = [permissions.AllowAny]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'is_box', 'is_featured']
    search_fields    = ['name', 'description']
    ordering_fields  = ['price', 'name', 'created_at']
    parser_classes   = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'featured', 'boxes']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(is_featured=True)[:6]
        serializer = ProductListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def boxes(self, request):
        qs = self.get_queryset().filter(is_box=True)
        serializer = ProductListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().prefetch_related('items__product')

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        try:
            from .notifications import notify_new_order
            notify_new_order(order)
        except Exception:
            pass
        read_serializer = OrderReadSerializer(order, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(Order.Status.choices):
            return Response({'error': 'Statut invalide.'}, status=400)
        order.status = new_status
        order.save(update_fields=['status'])
        return Response({'status': order.status, 'display': order.get_status_display()})


from rest_framework.decorators import api_view, permission_classes as pc
from rest_framework.permissions import AllowAny

@api_view(['POST'])
@pc([AllowAny])
def validate_promo(request):
    code = request.data.get('code', '').strip().upper()
    total = float(request.data.get('total', 0))

    try:
        promo = CodePromo.objects.get(code=code)
    except CodePromo.DoesNotExist:
        return Response({'valid': False, 'message': 'Code promo invalide.'}, status=400)

    valid, message = promo.is_valid(total)
    if not valid:
        return Response({'valid': False, 'message': message}, status=400)

    discount = promo.calculate_discount(total)
    return Response({
        'valid': True,
        'code': promo.code,
        'discount_type': promo.discount_type,
        'discount_value': float(promo.discount_value),
        'discount_amount': float(discount),
        'new_total': float(total - discount),
        'message': f"Code appliqué — {discount:,.0f} FCFA de réduction !",
    })


class CodePromoViewSet(viewsets.ModelViewSet):
    from .models import CodePromo as CP
    queryset = CP.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        from rest_framework import serializers
        class CodePromoSerializer(serializers.ModelSerializer):
            class Meta:
                from .models import CodePromo as CP2
                model = CP2
                fields = '__all__'
        return CodePromoSerializer


from .models import ZoneLivraison

class ZoneLivraisonViewSet(viewsets.ModelViewSet):
    queryset = ZoneLivraison.objects.filter(is_active=True).order_by('order')
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        from rest_framework import serializers
        class ZoneSerializer(serializers.ModelSerializer):
            class Meta:
                model = ZoneLivraison
                fields = '__all__'
        return ZoneSerializer

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


from .models import BonCadeau

class BonCadeauViewSet(viewsets.ModelViewSet):
    queryset = BonCadeau.objects.all().order_by('-created_at')

    def get_permissions(self):
        if self.action in ['create', 'validate_bon']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        from rest_framework import serializers
        class BonSerializer(serializers.ModelSerializer):
            class Meta:
                model = BonCadeau
                fields = '__all__'
        return BonSerializer

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def validate_bon(self, request):
        code = request.data.get('code', '').strip().upper()
        total = float(request.data.get('total', 0))
        try:
            bon = BonCadeau.objects.get(code=code)
        except BonCadeau.DoesNotExist:
            return Response({'valid': False, 'message': 'Bon cadeau invalide.'}, status=400)

        if not bon.is_paid:
            return Response({'valid': False, 'message': 'Ce bon cadeau n\'a pas encore été activé.'}, status=400)
        if bon.is_used:
            return Response({'valid': False, 'message': 'Ce bon cadeau a déjà été utilisé.'}, status=400)

        from django.utils import timezone
        if bon.expires_at and timezone.now() > bon.expires_at:
            return Response({'valid': False, 'message': 'Ce bon cadeau a expiré.'}, status=400)

        discount = min(float(bon.montant), total)
        return Response({
            'valid': True,
            'code': bon.code,
            'montant': float(bon.montant),
            'discount_amount': discount,
            'new_total': max(0, total - discount),
            'message': f'Bon cadeau appliqué — {discount:,.0f} FCFA de réduction !',
        })
