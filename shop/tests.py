from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Category, Product, Addon, Order, CodePromo, BonCadeau


class OrderApiTestCase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Pâtisserie", slug="patisserie")
        self.product = Product.objects.create(
            category=self.category, name="Gâteau Choco", slug="gateau-choco",
            price=Decimal("5000"), stock=10, is_available=True,
        )
        self.addon = Addon.objects.create(name="Bougies", price=Decimal("500"))
        self.product.available_addons.add(self.addon)

        self.url = '/api/shop/orders/'
        self.base_payload = {
            'customer_name': 'Koffi Adjoua',
            'customer_whatsapp': '+22900000000',
            'pickup_date': '2026-12-20',
            'pickup_time': '14:30',
        }

    def order_payload(self, **overrides):
        payload = {
            **self.base_payload,
            'items': [{'product_id': self.product.id, 'quantity': 1, 'selected_addon_ids': []}],
        }
        payload.update(overrides)
        return payload

    def test_create_order_with_addons(self):
        res = self.client.post(self.url, self.order_payload(
            items=[{'product_id': self.product.id, 'quantity': 2,
                    'selected_addon_ids': [self.addon.id]}]
        ), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data['total_price']), (5000 + 500) * 2)
        order = Order.objects.get(reference=res.data['reference'])
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().selected_addons[0]['name'], 'Bougies')

    def test_create_order_decrements_stock(self):
        res = self.client.post(self.url, self.order_payload(
            items=[{'product_id': self.product.id, 'quantity': 3, 'selected_addon_ids': []}]
        ), format='json')
        self.assertEqual(res.status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_create_order_rejects_insufficient_stock(self):
        res = self.client.post(self.url, self.order_payload(
            items=[{'product_id': self.product.id, 'quantity': 12, 'selected_addon_ids': []}]
        ), format='json')
        self.assertEqual(res.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_create_order_rejects_unavailable_product(self):
        self.product.is_available = False
        self.product.save()
        res = self.client.post(self.url, self.order_payload(), format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_order_rejects_invalid_addon(self):
        other_addon = Addon.objects.create(name="Non lié", price=Decimal("100"))
        res = self.client.post(self.url, self.order_payload(
            items=[{'product_id': self.product.id, 'quantity': 1,
                    'selected_addon_ids': [other_addon.id]}]
        ), format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_order_applies_promo_code(self):
        promo = CodePromo.objects.create(
            code='AEVENTS20', discount_type='percent', discount_value=Decimal("20"),
            max_uses=100,
        )
        res = self.client.post(self.url, self.order_payload(promo_code='aevents20'), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data['total_price']), 4000)
        self.assertEqual(Decimal(res.data['discount_amount']), 1000)
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)

    def test_create_order_rejects_exhausted_promo(self):
        CodePromo.objects.create(
            code='EPUISE', discount_type='fixed', discount_value=Decimal("500"),
            max_uses=1, used_count=1,
        )
        res = self.client.post(self.url, self.order_payload(promo_code='EPUISE'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_order_rejects_unknown_promo(self):
        res = self.client.post(self.url, self.order_payload(promo_code='INCONNU'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_order_applies_bon_cadeau(self):
        bon = BonCadeau.objects.create(
            code='GIFT-ABCDEF', montant=Decimal("2000"), is_paid=True,
        )
        res = self.client.post(self.url, self.order_payload(bon_code='gift-abcdef'), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data['total_price']), 3000)
        bon.refresh_from_db()
        self.assertTrue(bon.is_used)

    def test_create_order_rejects_unpaid_bon(self):
        BonCadeau.objects.create(code='GIFT-NONPAY', montant=Decimal("2000"), is_paid=False)
        res = self.client.post(self.url, self.order_payload(bon_code='GIFT-NONPAY'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_order_rejects_used_bon(self):
        BonCadeau.objects.create(code='GIFT-UTILISE', montant=Decimal("2000"), is_used=True, is_paid=True)
        res = self.client.post(self.url, self.order_payload(bon_code='GIFT-UTILISE'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_promo_and_bon_combined_not_below_zero(self):
        CodePromo.objects.create(
            code='GROSPROMO', discount_type='fixed', discount_value=Decimal("5000"),
            max_uses=10,
        )
        bon = BonCadeau.objects.create(
            code='GIFT-COMBO', montant=Decimal("5000"), is_paid=True,
        )
        res = self.client.post(self.url, self.order_payload(
            promo_code='GROSPROMO', bon_code='GIFT-COMBO'
        ), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data['total_price']), 0)
        self.assertEqual(Decimal(res.data['discount_amount']), 5000)
        bon.refresh_from_db()
        self.assertTrue(bon.is_used)

    def test_orders_get_unique_references(self):
        r1 = self.client.post(self.url, self.order_payload(), format='json')
        r2 = self.client.post(self.url, self.order_payload(), format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_cancel_order_restores_stock(self):
        admin = User.objects.create_superuser('admin', 'a@a.com', 'password123')
        self.client.force_authenticate(admin)
        res = self.client.post(self.url, self.order_payload(
            items=[{'product_id': self.product.id, 'quantity': 4, 'selected_addon_ids': []}]
        ), format='json')
        self.assertEqual(res.status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)

        res = self.client.patch(
            f"/api/shop/orders/{res.data['id']}/update_status/",
            {'status': 'cancelled'}, format='json'
        )
        self.assertEqual(res.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
