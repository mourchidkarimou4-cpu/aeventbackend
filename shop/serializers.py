from rest_framework import serializers
from .models import (
    Category, Addon, Product, Order, OrderItem,
    CodePromo, ZoneLivraison, BonCadeau,
    ProgrammeFidelite, Parrainage, Pack, PackItem,
)


def absolute_file_url(request, value):
    if not value:
        return None
    try:
        url = value.url
    except Exception:
        url = str(value)
    if not url:
        return None
    if url.startswith(('http://', 'https://')):
        return url
    if request:
        return request.build_absolute_uri(url)
    return url


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_image(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)


class AddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Addon
        fields = '__all__'


class BaseProductSerializer(serializers.ModelSerializer):
    """Serializer de base pour les produits, contenant les champs communs."""
    image = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    available_addons = AddonSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'image', 'image_url', 'price',
            'category_name', 'category_slug', 'is_box', 
            'is_featured', 'is_available', 'preparation_time_hours',
            'min_quantity', 'stock', 'available_addons',
        ]

    def get_image_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)


class ProductListSerializer(BaseProductSerializer):
    """Serializer léger pour le listage des produits."""
    class Meta(BaseProductSerializer.Meta):
        pass


class ProductDetailSerializer(BaseProductSerializer):
    """Serializer complet pour le détail d'un produit."""
    class Meta(BaseProductSerializer.Meta):
        fields = '__all__'

# Alias pour compatibilité descendante
ProductSerializer = ProductDetailSerializer


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    selected_addon_ids = serializers.ListField(
        child=serializers.IntegerField(), default=list
    )


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemCreateSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = [
            'customer_name', 'customer_whatsapp', 'customer_email',
            'customer_note', 'pickup_date', 'pickup_time', 'items',
        ]
        extra_kwargs = {
            'customer_name': {'required': True},
            'customer_whatsapp': {'required': True},
            'pickup_date': {'required': True},
            'pickup_time': {'required': True},
        }

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)

        total = 0
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            quantity = item_data['quantity']
            unit_price = product.price

            # Récupérer les addons sélectionnés
            addon_ids = item_data.get('selected_addon_ids', [])
            selected_addons = Addon.objects.filter(id__in=addon_ids)
            addons_snapshot = [
                {'id': a.id, 'name': a.name, 'price': float(a.price)}
                for a in selected_addons
            ]
            addons_total = sum(a.price for a in selected_addons)

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                selected_addons=addons_snapshot,
                addons_total=addons_total,
            )

            total += (unit_price + addons_total) * quantity

        order.total_price = total
        order.save(update_fields=['total_price'])
        return order


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_name', 'product_slug', 'product_image',
            'quantity', 'unit_price', 'selected_addons',
            'addons_total', 'line_total',
        ]

    def get_product_image(self, obj):
        return absolute_file_url(self.context.get('request'), obj.product.image)


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'reference', 'customer_name', 'customer_whatsapp',
            'customer_email', 'customer_note', 'status',
            'total_price', 'pickup_date', 'pickup_time',
            'items', 'created_at', 'updated_at',
        ]


class CodePromoSerializer(serializers.ModelSerializer):
    discount_display = serializers.SerializerMethodField()

    class Meta:
        model = CodePromo
        fields = '__all__'

    def get_discount_display(self, obj):
        if obj.discount_type == 'percent':
            return f"{obj.discount_value}%"
        return f"{obj.discount_value} FCFA"


class ZoneLivraisonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZoneLivraison
        fields = '__all__'


class BonCadeauSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonCadeau
        fields = '__all__'


class ProgrammeFideliteSerializer(serializers.ModelSerializer):
    niveau = serializers.SerializerMethodField()
    points_reduction = serializers.IntegerField(source='points_pour_reduction', read_only=True)

    class Meta:
        model = ProgrammeFidelite
        fields = '__all__'

    def get_niveau(self, obj):
        return {'label': obj.niveau[0], 'color': obj.niveau[1]}


class ParrainageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parrainage
        fields = '__all__'


class PackItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackItem
        fields = '__all__'


class PackSerializer(serializers.ModelSerializer):
    items = PackItemSerializer(many=True, read_only=True)
    image = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Pack
        fields = '__all__'

    def get_image_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)
