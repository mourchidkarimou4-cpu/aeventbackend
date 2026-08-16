from decimal import Decimal
from django.db import transaction
from django.utils import timezone
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
    promo_code = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    bon_code = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    class Meta:
        model = Order
        fields = [
            'customer_name', 'customer_whatsapp', 'customer_email',
            'customer_note', 'pickup_date', 'pickup_time', 'items',
            'promo_code', 'bon_code',
        ]
        extra_kwargs = {
            'customer_name': {'required': True},
            'customer_whatsapp': {'required': True},
            'pickup_date': {'required': True},
            'pickup_time': {'required': True},
        }

    def _apply_code_promo(self, order, code, total):
        try:
            promo = CodePromo.objects.select_for_update().get(code__iexact=code)
        except CodePromo.DoesNotExist:
            raise serializers.ValidationError({'promo_code': 'Ce code promo n\'existe pas.'})
        valid, message = promo.is_valid(total)
        if not valid:
            raise serializers.ValidationError({'promo_code': message})
        discount = promo.calculate_discount(total)
        promo.used_count += 1
        promo.save(update_fields=['used_count'])
        return discount

    def _apply_bon_cadeau(self, code, remaining):
        try:
            bon = BonCadeau.objects.select_for_update().get(code__iexact=code)
        except BonCadeau.DoesNotExist:
            raise serializers.ValidationError({'bon_code': 'Ce bon cadeau n\'existe pas.'})
        if not bon.is_paid:
            raise serializers.ValidationError({'bon_code': 'Ce bon cadeau n\'a pas encore été payé.'})
        if bon.is_used:
            raise serializers.ValidationError({'bon_code': 'Ce bon cadeau a déjà été utilisé.'})
        if bon.expires_at and timezone.now() > bon.expires_at:
            raise serializers.ValidationError({'bon_code': 'Ce bon cadeau a expiré.'})
        bon.is_used = True
        bon.save(update_fields=['is_used'])
        return min(bon.montant, remaining)

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        promo_code = (validated_data.pop('promo_code', '') or '').strip().upper()
        bon_code = (validated_data.pop('bon_code', '') or '').strip().upper()

        with transaction.atomic():
            order = Order.objects.create(**validated_data)

            total = Decimal('0')
            for item_data in items_data:
                try:
                    product = Product.objects.select_for_update().get(id=item_data['product_id'])
                except Product.DoesNotExist:
                    raise serializers.ValidationError(
                        {'items': f"Produit {item_data['product_id']} introuvable."}
                    )
                quantity = item_data['quantity']

                if not product.is_available:
                    raise serializers.ValidationError(
                        {'items': f"Le produit « {product.name} » n'est plus disponible."}
                    )
                if quantity < (product.min_quantity or 1):
                    raise serializers.ValidationError(
                        {'items': f"Quantité minimale de {product.min_quantity} requise pour « {product.name} »."}
                    )
                if product.stock is not None:
                    if product.stock < quantity:
                        raise serializers.ValidationError(
                            {'items': f"Stock insuffisant pour « {product.name} » "
                                      f"(stock restant : {product.stock})."}
                        )
                    product.stock -= quantity
                    product.save(update_fields=['stock'])

                # Valider que les addons appartiennent bien au produit
                addon_ids = list(dict.fromkeys(item_data.get('selected_addon_ids', [])))
                valid_addon_ids = set(product.available_addons.values_list('id', flat=True))
                invalid_ids = [aid for aid in addon_ids if aid not in valid_addon_ids]
                if invalid_ids:
                    raise serializers.ValidationError(
                        {'items': f"Accompagnements invalides pour « {product.name} » : {invalid_ids}."}
                    )
                selected_addons = list(Addon.objects.filter(id__in=addon_ids).order_by('id'))
                addons_snapshot = [
                    {'id': a.id, 'name': a.name, 'price': float(a.price)}
                    for a in selected_addons
                ]
                addons_total = sum((a.price for a in selected_addons), Decimal('0'))

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    selected_addons=addons_snapshot,
                    addons_total=addons_total,
                )

                total += (product.price + addons_total) * quantity

            discount = Decimal('0')
            if promo_code:
                discount += self._apply_code_promo(order, promo_code, total)
            if bon_code:
                discount += self._apply_bon_cadeau(bon_code, total - discount)

            discount = min(discount, total)
            order.total_price = total - discount
            order.discount_amount = discount
            order.promo_code = promo_code
            order.bon_code = bon_code
            order.save(update_fields=['total_price', 'discount_amount', 'promo_code', 'bon_code'])
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
    whatsapp_notify_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'reference', 'customer_name', 'customer_whatsapp',
            'customer_email', 'customer_note', 'status',
            'total_price', 'discount_amount', 'promo_code', 'bon_code',
            'pickup_date', 'pickup_time',
            'items', 'whatsapp_notify_url', 'created_at', 'updated_at',
        ]

    def get_whatsapp_notify_url(self, obj):
        from .notifications import order_whatsapp_notify_url
        return order_whatsapp_notify_url(obj, items=obj.items.all())


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
        fields = [
            'id', 'code', 'montant', 'acheteur_nom', 'acheteur_wa',
            'destinataire_nom', 'destinataire_wa', 'message',
            'is_used', 'is_paid', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'code', 'created_at']
        extra_kwargs = {'montant': {'min_value': Decimal('1')}}

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        is_staff = bool(request and request.user and getattr(request.user, 'is_staff', False))
        if not is_staff:
            # Un client ne peut ni se payer un bon, ni le marquer utilisé/expirer
            for name in ('is_used', 'is_paid', 'expires_at'):
                fields[name].read_only = True
        return fields


class ProgrammeFideliteSerializer(serializers.ModelSerializer):
    niveau = serializers.SerializerMethodField()
    points_reduction = serializers.IntegerField(source='points_pour_reduction', read_only=True)

    class Meta:
        model = ProgrammeFidelite
        fields = [
            'id', 'client_nom', 'client_wa', 'points', 'total_commandes',
            'niveau', 'points_reduction', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        is_staff = bool(request and request.user and getattr(request.user, 'is_staff', False))
        if not is_staff:
            # Les points ne s'obtiennent qu'avec des commandes réelles (add_points)
            fields['points'].read_only = True
            fields['total_commandes'].read_only = True
        return fields

    def get_niveau(self, obj):
        return {'label': obj.niveau[0], 'color': obj.niveau[1]}


class ParrainageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parrainage
        fields = [
            'id', 'parrain_nom', 'parrain_wa', 'filleul_nom', 'filleul_wa',
            'code', 'points_gagnes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        is_staff = bool(request and request.user and getattr(request.user, 'is_staff', False))
        if not is_staff:
            # Code généré côté serveur, points crédités par l'admin
            fields['code'].read_only = True
            fields['points_gagnes'].read_only = True
        return fields

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method == 'POST':
            wa = attrs.get('parrain_wa')
            if wa and Parrainage.objects.filter(parrain_wa__iexact=wa).exists():
                raise serializers.ValidationError(
                    {'parrain_wa': 'Un code de parrainage existe déjà pour ce numéro.'}
                )
        return attrs


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
