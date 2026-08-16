from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Formation, Reservation


class ReservationApiTestCase(APITestCase):
    def setUp(self):
        self.formation = Formation.objects.create(
            title="Pâtisserie débutant",
            slug="patisserie-debutant",
            description="Apprendre la pâtisserie",
            total_seats=10,
            price=Decimal("25000"),
            start_datetime=timezone.now() + timedelta(days=10),
            end_datetime=timezone.now() + timedelta(days=11),
            status=Formation.Status.PUBLISHED,
        )
        self.url = '/api/academy/reservations/'
        self.payload = {
            'formation': self.formation.id,
            'participant_name': 'Aïcha Moussa',
            'participant_whatsapp': '+22991111111',
            'participant_email': 'aicha@example.com',
        }

    def test_create_reservation_increments_reserved_seats(self):
        res = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.formation.refresh_from_db()
        self.assertEqual(self.formation.reserved_seats, 1)

    def test_duplicate_whatsapp_rejected(self):
        res = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(res.status_code, 201)
        res = self.client.post(self.url, {**self.payload, 'participant_name': 'Autre'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_reservation_on_full_formation_goes_waitlist(self):
        full = Formation.objects.create(
            title="Formation complète",
            slug="formation-complete",
            description="Complète",
            total_seats=1,
            price=Decimal("10000"),
            start_datetime=timezone.now() + timedelta(days=5),
            end_datetime=timezone.now() + timedelta(days=6),
            status=Formation.Status.FULL,
        )
        Reservation.objects.create(
            formation=full, participant_name="Premier", participant_whatsapp="+22911111110",
            status=Reservation.Status.CONFIRMED,
        )
        res = self.client.post(self.url, {
            'formation': full.id,
            'participant_name': 'Deuxième',
            'participant_whatsapp': '+22922222222',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['status'], Reservation.Status.WAITLIST)

    def test_reservation_on_past_formation_rejected(self):
        past = Formation.objects.create(
            title="Formation passée",
            slug="formation-passee",
            description="Passée",
            total_seats=10,
            price=Decimal("10000"),
            start_datetime=timezone.now() - timedelta(days=1),
            end_datetime=timezone.now() - timedelta(hours=2),
            status=Formation.Status.PUBLISHED,
        )
        res = self.client.post(self.url, {
            'formation': past.id,
            'participant_name': 'Tardif',
            'participant_whatsapp': '+22933333333',
        }, format='json')
        self.assertEqual(res.status_code, 400)
