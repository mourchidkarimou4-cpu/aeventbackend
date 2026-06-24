from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField, F
from .models import Formation, Reservation
from .serializers import (
    FormationListSerializer, FormationDetailSerializer,
    ReservationCreateSerializer, ReservationReadSerializer
)


class FormationViewSet(viewsets.ModelViewSet):
    # 🔧 OPTIMISATION: Utiliser le manager with_stats() pour éviter N+1 queries
    queryset = Formation.objects.with_stats().filter(
        status__in=['published', 'full']
    ).prefetch_related('reservations')
    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['level', 'is_online', 'is_featured']
    search_fields = ['title', 'description', 'instructor_name']
    ordering_fields = ['start_datetime', 'price']

    def get_serializer_class(self):
        from rest_framework.permissions import IsAdminUser
        if self.request.user and self.request.user.is_staff:
            from .serializers import FormationAdminSerializer
            return FormationAdminSerializer
        if self.action == 'retrieve':
            return FormationDetailSerializer
        return FormationListSerializer

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        qs = self.get_queryset().filter(
            start_datetime__gt=timezone.now()
        ).order_by('start_datetime')[:6]
        serializer = FormationListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().select_related('formation')

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reservation = serializer.save()
        read_s = ReservationReadSerializer(reservation, context={'request': request})
        return Response(read_s.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def confirm_payment(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = Reservation.Status.PAID
        reservation.amount_paid = request.data.get('amount_paid', reservation.formation.current_price)
        reservation.payment_method = request.data.get('payment_method', '')
        reservation.payment_ref = request.data.get('payment_ref', '')
        reservation.payment_date = timezone.now()
        reservation.save()
        return Response({'status': 'paid', 'reference': reservation.reference})


from .models import FormationPresentielle, DossierCandidature
from .serializers import FormationPresentiellSerializer, DossierCandidatureSerializer

class FormationPresentiellViewSet(viewsets.ModelViewSet):
    queryset = FormationPresentielle.objects.filter(is_active=True)
    serializer_class = FormationPresentiellSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class DossierCandidatureViewSet(viewsets.ModelViewSet):
    queryset = DossierCandidature.objects.all().order_by('-created_at')
    serializer_class = DossierCandidatureSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        formation_id = self.request.query_params.get('formation')
        if formation_id:
            qs = qs.filter(formation_id=formation_id)
        return qs
