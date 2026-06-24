import logging
from rest_framework import viewsets, permissions, status, filters, parsers
from rest_framework.decorators import action, api_view, permission_classes as pc
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import (
    Category, Product, Order, Addon, CodePromo, 
    ZoneLivraison, BonCadeau, ProgrammeFidelite, 
    Parrainage, Pack, PackItem
)
from .serializers import (
    CategorySerializer, AddonSerializer, ProductSerializer, ProductListSerializer,
    ProductDetailSerializer, OrderCreateSerializer, OrderReadSerializer, 
    CodePromoSerializer, ZoneLivraisonSerializer, BonCadeauSerializer, 
    ProgrammeFideliteSerializer, ParrainageSerializer, PackSerializer, 
    PackItemSerializer,
)

logger = logging.getLogger(__name__)

class BaseShopViewSet(viewsets.ModelViewSet):
    """ViewSet de base pour le shop avec gestion standard des permissions."""
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class CategoryViewSet(BaseShopViewSet):
    queryset = Category.objects.all().order_by('order')
    serializer_class = CategorySerializer


class AddonViewSet(BaseShopViewSet):
    queryset = Addon.objects.all().order_by('name')
    serializer_class = AddonSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().select_related('category').prefetch_related('available_addons')
    lookup_field = 'pk'
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'is_box', 'is_featured']
    search_fields    = ['name', 'description']
    ordering_fields  = ['price', 'name', 'created_at']
    parser_classes   = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

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
        except Exception as e:
            logger.error(f"Erreur lors de la notification de commande {order.reference}: {str(e)}")
            
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


@api_view(['POST'])
@pc([permissions.AllowAny])
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
    queryset = CodePromo.objects.all().order_by('-created_at')
    serializer_class = CodePromoSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ZoneLivraisonViewSet(BaseShopViewSet):
    queryset = ZoneLivraison.objects.filter(is_active=True).order_by('order')
    serializer_class = ZoneLivraisonSerializer


class BonCadeauViewSet(viewsets.ModelViewSet):
    queryset = BonCadeau.objects.all().order_by('-created_at')
    serializer_class = BonCadeauSerializer

    def get_permissions(self):
        if self.action in ['create', 'validate_bon']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

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


class FideliteViewSet(viewsets.ModelViewSet):
    queryset = ProgrammeFidelite.objects.all().order_by('-points')
    serializer_class = ProgrammeFideliteSerializer

    def get_permissions(self):
        if self.action in ['check', 'create']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def check(self, request):
        wa = request.data.get('whatsapp', '').strip()
        if not wa:
            return Response({'error': 'WhatsApp requis.'}, status=400)
        try:
            fidelite = ProgrammeFidelite.objects.get(client_wa=wa)
            return Response({
                'found': True,
                'nom': fidelite.client_nom,
                'points': fidelite.points,
                'niveau': fidelite.niveau[0],
                'color': fidelite.niveau[1],
                'commandes': fidelite.total_commandes,
                'reduction_disponible': fidelite.points_pour_reduction,
            })
        except ProgrammeFidelite.DoesNotExist:
            return Response({'found': False, 'message': 'Pas encore inscrit au programme.'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def add_points(self, request):
        wa = request.data.get('whatsapp', '').strip()
        nom = request.data.get('nom', '').strip()
        points = int(request.data.get('points', 0))
        if not wa or not points:
            return Response({'error': 'WhatsApp et points requis.'}, status=400)
        fidelite, created = ProgrammeFidelite.objects.get_or_create(
            client_wa=wa,
            defaults={'client_nom': nom, 'points': 0, 'total_commandes': 0}
        )
        fidelite.points += points
        fidelite.total_commandes += 1
        fidelite.save()
        return Response({
            'success': True,
            'points': fidelite.points,
            'niveau': fidelite.niveau[0],
        })


class ParrainageViewSet(viewsets.ModelViewSet):
    queryset = Parrainage.objects.all().order_by('-created_at')
    serializer_class = ParrainageSerializer

    def get_permissions(self):
        if self.action in ['create', 'list']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class PackViewSet(viewsets.ModelViewSet):
    queryset = Pack.objects.filter(is_active=True).prefetch_related('items')
    serializer_class = PackSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        pack = serializer.save()
        items_data = self.request.data.get('items', [])
        for item in items_data:
            PackItem.objects.create(
                pack=pack,
                quantite=item.get('quantite', 1),
                nom_item=item.get('nom_item', ''),
                ordre=item.get('ordre', 0),
            )

    def perform_update(self, serializer):
        pack = serializer.save()
        items_data = self.request.data.get('items', None)
        if items_data is not None:
            pack.items.all().delete()
            for item in items_data:
                PackItem.objects.create(
                    pack=pack,
                    quantite=item.get('quantite', 1),
                    nom_item=item.get('nom_item', ''),
                    ordre=item.get('ordre', 0),
                )
