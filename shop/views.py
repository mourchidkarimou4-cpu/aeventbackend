import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, permissions, status, filters, parsers, generics
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.decorators import action
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

    def get_queryset(self):
        qs = Product.objects.all().select_related('category').prefetch_related('available_addons')
        user = self.request.user
        if not (user and user.is_staff):
            qs = qs.filter(is_available=True)
        return qs

    def get_object(self):
        """Accepte l'identifiant (admin) OU le slug (pages publiques)."""
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        try:
            return generics.get_object_or_404(queryset, pk=int(lookup_value))
        except (TypeError, ValueError):
            return generics.get_object_or_404(queryset, slug=lookup_value)

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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'reference', 'customer_whatsapp']
    search_fields = ['reference', 'customer_name', 'customer_whatsapp']
    ordering_fields = ['created_at', 'total_price', 'pickup_date']

    def get_permissions(self):
        if self.action in ['create', 'track', 'history']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_throttles(self):
        if self.action in ['create', 'track', 'history']:
            self.throttle_scope = 'orders'
            return [ScopedRateThrottle()]
        return []

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

        from .order_transitions import apply_status_transition
        ok, error = apply_status_transition(order, new_status)
        if not ok:
            return Response({'error': error}, status=400)
        order.save(update_fields=['status'])
        return Response({'status': order.status, 'display': order.get_status_display()})

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def track(self, request):
        """Suivi public d'une commande : référence + numéro WhatsApp du client."""
        reference = request.query_params.get('reference', '').strip().upper()
        whatsapp = request.query_params.get('customer_whatsapp', '').strip()
        if not reference or not whatsapp:
            return Response({'error': 'Référence et numéro WhatsApp requis.'}, status=400)
        try:
            order = Order.objects.prefetch_related('items__product').get(reference=reference)
        except Order.DoesNotExist:
            return Response({'error': 'Aucune commande trouvée avec cette référence.'}, status=404)
        if order.customer_whatsapp.strip() != whatsapp:
            return Response({'error': 'Numéro WhatsApp non associé à cette commande.'}, status=403)
        serializer = OrderReadSerializer(order, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def history(self, request):
        """Historique public des commandes d'un client (identité = numéro WhatsApp)."""
        whatsapp = request.query_params.get('customer_whatsapp', '').strip()
        if not whatsapp:
            return Response({'error': 'Numéro WhatsApp requis.'}, status=400)
        orders = Order.objects.filter(customer_whatsapp=whatsapp).prefetch_related('items__product').order_by('-created_at')
        serializer = OrderReadSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)


class ValidatePromoView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'promo_validate'

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        try:
            total = Decimal(str(request.data.get('total', 0)))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'error': 'Montant invalide.'}, status=400)

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
            'message': f"Code appliqué — {float(discount):,.0f} FCFA de réduction !",
        })


class CodePromoViewSet(BaseShopViewSet):
    queryset = CodePromo.objects.all().order_by('-created_at')
    serializer_class = CodePromoSerializer


class ZoneLivraisonViewSet(BaseShopViewSet):
    queryset = ZoneLivraison.objects.filter(is_active=True).order_by('order')
    serializer_class = ZoneLivraisonSerializer


class BonCadeauViewSet(viewsets.ModelViewSet):
    queryset = BonCadeau.objects.all().order_by('-created_at')
    serializer_class = BonCadeauSerializer
    throttle_scope = 'public_post'

    def get_permissions(self):
        if self.action in ['create', 'validate_bon']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def validate_bon(self, request):
        code = request.data.get('code', '').strip().upper()
        try:
            total = Decimal(str(request.data.get('total', 0)))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'error': 'Montant invalide.'}, status=400)
        try:
            bon = BonCadeau.objects.get(code__iexact=code)
        except BonCadeau.DoesNotExist:
            return Response({'valid': False, 'message': 'Bon cadeau invalide.'}, status=400)

        if not bon.is_paid:
            return Response({'valid': False, 'message': 'Ce bon cadeau n\'a pas encore été activé.'}, status=400)
        if bon.is_used:
            return Response({'valid': False, 'message': 'Ce bon cadeau a déjà été utilisé.'}, status=400)

        if bon.expires_at and timezone.now() > bon.expires_at:
            return Response({'valid': False, 'message': 'Ce bon cadeau a expiré.'}, status=400)

        discount = min(bon.montant, total)
        return Response({
            'valid': True,
            'code': bon.code,
            'montant': float(bon.montant),
            'discount_amount': float(discount),
            'new_total': float(total - discount),
            'message': f'Bon cadeau appliqué — {float(discount):,.0f} FCFA de réduction !',
        })


class FideliteViewSet(viewsets.ModelViewSet):
    queryset = ProgrammeFidelite.objects.all().order_by('-points')
    serializer_class = ProgrammeFideliteSerializer
    throttle_scope = 'public_post'

    def get_permissions(self):
        if self.action in ['check']:
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
        try:
            points = int(request.data.get('points', 0))
        except (TypeError, ValueError):
            return Response({'error': 'Points invalides.'}, status=400)
        if not wa or points <= 0:
            return Response({'error': 'WhatsApp et points (positifs) requis.'}, status=400)
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
    throttle_scope = 'public_post'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['parrain_wa']
    search_fields = ['parrain_nom', 'filleul_nom', 'parrain_wa', 'code']

    def get_permissions(self):
        if self.action in ['create', 'by_wa']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def by_wa(self, request):
        """Retrouve le code de parrainage associé à un numéro WhatsApp."""
        wa = request.query_params.get('parrain_wa', '').strip()
        if not wa:
            return Response({'error': 'WhatsApp requis.'}, status=400)
        parrainage = Parrainage.objects.filter(parrain_wa=wa).order_by('-created_at').first()
        if not parrainage:
            return Response({'found': False, 'message': 'Aucun code de parrainage trouvé pour ce numéro.'}, status=404)
        return Response({
            'found': True,
            'code': parrainage.code,
            'parrain_nom': parrainage.parrain_nom,
            'parrain_wa': parrainage.parrain_wa,
        })


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
