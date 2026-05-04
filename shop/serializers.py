from rest_framework import serializers
from decimal import Decimal
from .models import Category, Addon, Product, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'order', 'product_count']

    def get_product_count(self, obj):
        return obj.products.filter(is_available=True).count()


class AddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Addon
        fields = ['id', 'name', 'price', 'description']


class ProductSerializer(serializers.ModelSerializer):
    category      = CategorySerializer(read_only=True)
    category_id   = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    available_addons = AddonSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price',
            'image', 'image_gallery',
            'is_box', 'box_contents', 'min_quantity',
            'preparation_time_hours',
            'is_available', 'is_featured', 'stock',
            'category', 'category_id',
            'available_addons',
        ]

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    """Version allégée pour les listings (performances)."""
    category_name    = serializers.CharField(source='category.name', read_only=True)
    available_addons = AddonSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'image',
            'is_box', 'is_featured', 'is_available',
            'min_quantity', 'preparation_time_hours',
            'category_name', 'available_addons',
        ]


# ──────────────────────────────────────────────
# Commandes
# ──────────────────────────────────────────────

class OrderItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_image',
            'quantity', 'unit_price', 'selected_addons',
            'addons_total', 'line_total',
        ]


class OrderItemCreateSerializer(serializers.Serializer):
    """Payload attendu depuis le frontend pour chaque ligne de panier."""
    product_id      = serializers.IntegerField()
    quantity        = serializers.IntegerField(min_value=1, max_value=100)
    selected_addon_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        default=list
    )


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemCreateSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = [
            'customer_name', 'customer_whatsapp', 'customer_email',
            'customer_note', 'pickup_date', 'pickup_time',
            'items',
        ]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("La commande doit contenir au moins un produit.")
        return items

    def validate(self, attrs):
        from django.utils import timezone
        from datetime import date, timedelta
        pickup_date = attrs.get('pickup_date')
        if pickup_date and pickup_date < date.today():
            raise serializers.ValidationError(
                {"pickup_date": "La date de retrait ne peut pas être dans le passé."}
            )
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items')

        # Créer l'Order sans total (calculé après)
        order = Order.objects.create(total_price=0, **validated_data)

        grand_total = Decimal('0')

        for item_data in items_data:
            product_id         = item_data['product_id']
            quantity           = item_data['quantity']
            selected_addon_ids = item_data.get('selected_addon_ids', [])

            # Récupérer le produit
            try:
                product = Product.objects.get(pk=product_id, is_available=True)
            except Product.DoesNotExist:
                raise serializers.ValidationError(
                    {"items": f"Produit ID {product_id} introuvable ou indisponible."}
                )

            unit_price = product.price

            # Calculer les addons
            addons_snapshot = []
            addons_total    = Decimal('0')

            if selected_addon_ids:
                # On ne récupère que les addons effectivement disponibles sur ce produit
                valid_addons = product.available_addons.filter(
                    pk__in=selected_addon_ids, is_active=True
                )
                for addon in valid_addons:
                    addons_total += addon.price
                    addons_snapshot.append({
                        'id':    addon.pk,
                        'name':  addon.name,
                        'price': str(addon.price),
                    })

            line_total = (unit_price + addons_total) * quantity
            grand_total += line_total

            OrderItem.objects.create(
                order           = order,
                product         = product,
                quantity        = quantity,
                unit_price      = unit_price,
                selected_addons = addons_snapshot,
                addons_total    = addons_total,
            )

        # Mettre à jour le total
        order.total_price = grand_total
        order.save(update_fields=['total_price'])

        return order


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'reference', 'status', 'status_display',
            'customer_name', 'customer_whatsapp', 'customer_email', 'customer_note',
            'pickup_date', 'pickup_time',
            'total_price', 'items',
            'created_at', 'updated_at',
        ]
