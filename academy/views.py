from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import F, Prefetch, Count
from decimal import Decimal, InvalidOperation
from .models import Formation, Reservation
from .serializers import (
    FormationListSerializer, FormationDetailSerializer,
    ReservationCreateSerializer, ReservationReadSerializer
)


class FormationViewSet(viewsets.ModelViewSet):
    queryset = Formation.objects.all()

    # 🔧 OPTIMISATION: Utiliser le manager with_stats() pour éviter N+1 queries
    def get_queryset(self):
        qs = Formation.objects.with_stats()
        if self.request.user and self.request.user.is_staff:
            # prefetch filtré : les compteurs viennent de with_stats(), on ne charge
            # que les réservations non annulées pour le détail admin
            return qs.prefetch_related(
                Prefetch('reservations', queryset=Reservation.objects.exclude(
                    status=Reservation.Status.CANCELLED
                ))
            )
        return qs.filter(status__in=['published', 'full'])

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['level', 'is_online', 'is_featured']
    search_fields = ['title', 'description', 'instructor_name']
    ordering_fields = ['start_datetime', 'price']

    def get_serializer_class(self):
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['formation', 'status']
    ordering_fields = ['created_at', 'participant_name']

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_throttles(self):
        if self.action == 'create':
            self.throttle_scope = 'reservation'
            return [ScopedRateThrottle()]
        return []

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        formation_id = serializer.validated_data['formation'].id
        data = {k: v for k, v in serializer.validated_data.items() if k != 'formation'}

        with transaction.atomic():
            formation = Formation.objects.select_for_update().get(pk=formation_id)
            if formation.start_datetime <= timezone.now():
                raise serializers.ValidationError(
                    "Les inscriptions pour cette formation sont closes."
                )
            if formation.status not in ('published', 'full'):
                raise serializers.ValidationError("Formation non disponible.")
            status_value = (
                Reservation.Status.WAITLIST if formation.is_full
                else Reservation.Status.PENDING
            )
            try:
                reservation = Reservation.objects.create(
                    formation=formation, status=status_value, **data
                )
            except IntegrityError:
                raise serializers.ValidationError(
                    "Vous êtes déjà inscrit(e) à cette formation."
                )
            formation.reserved_seats = F('reserved_seats') + 1
            formation.save(update_fields=['reserved_seats'])

        read_s = ReservationReadSerializer(reservation, context={'request': request})
        return Response(read_s.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def confirm_payment(self, request, pk=None):
        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().get(pk=pk)
            formation = Formation.objects.select_for_update().get(pk=reservation.formation_id)

            if reservation.status == Reservation.Status.CANCELLED:
                return Response({'error': 'Cette réservation est annulée.'}, status=400)
            if formation.available_seats == 0 and reservation.status != Reservation.Status.PAID:
                return Response({'error': 'Cette formation est complète.'}, status=400)

            amount = request.data.get('amount_paid')
            if amount in (None, ''):
                amount = reservation.formation.current_price
            try:
                amount = Decimal(str(amount))
            except (InvalidOperation, TypeError, ValueError):
                return Response({'error': 'Montant invalide.'}, status=400)
            amount = min(amount, reservation.formation.current_price)

            reservation.status = Reservation.Status.PAID
            reservation.amount_paid = amount
            reservation.payment_method = request.data.get('payment_method', '')
            reservation.payment_ref = request.data.get('payment_ref', '')
            reservation.payment_date = timezone.now()
            reservation.save()
        return Response({'status': 'paid', 'reference': reservation.reference})


from .models import FormationPresentielle, DossierCandidature
from .serializers import FormationPresentiellSerializer, DossierCandidatureSerializer

class FormationPresentiellViewSet(viewsets.ModelViewSet):
    serializer_class = FormationPresentiellSerializer
    queryset = FormationPresentielle.objects.all()

    def get_queryset(self):
        qs = FormationPresentielle.objects.annotate(
            _places_inscrites=Count('dossiers')
        )
        if self.request.user and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True)

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

    def get_throttles(self):
        if self.action == 'create':
            self.throttle_scope = 'candidature'
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        qs = super().get_queryset()
        formation_id = self.request.query_params.get('formation')
        if formation_id:
            qs = qs.filter(formation_id=formation_id)
        return qs
