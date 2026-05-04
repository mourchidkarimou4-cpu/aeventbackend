from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from shop.models import Order, Product
from events.models import QuoteRequest
from academy.models import Formation, Reservation
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta


class DashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0)

        # Commandes
        orders = Order.objects.all()
        orders_month = orders.filter(created_at__gte=month_start)
        ca_total = orders.filter(status='completed').aggregate(s=Sum('total_price'))['s'] or 0
        ca_month = orders_month.filter(status='completed').aggregate(s=Sum('total_price'))['s'] or 0

        # Devis
        quotes = QuoteRequest.objects.all()

        # Academy
        reservations = Reservation.objects.filter(status='paid')

        # Produits
        products = Product.objects.filter(is_available=True)

        return Response({
            'orders': {
                'total':   orders.count(),
                'pending': orders.filter(status='pending').count(),
                'month':   orders_month.count(),
                'ca_total': float(ca_total),
                'ca_month': float(ca_month),
            },
            'quotes': {
                'total': quotes.count(),
                'new':   quotes.filter(status='new').count(),
            },
            'academy': {
                'reservations': reservations.count(),
                'revenue': float(reservations.aggregate(s=Sum('amount_paid'))['s'] or 0),
            },
            'products': {
                'total': products.count(),
                'featured': products.filter(is_featured=True).count(),
            },
        })
