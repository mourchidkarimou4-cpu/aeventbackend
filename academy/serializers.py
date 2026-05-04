from rest_framework import serializers
from django.utils import timezone
from .models import Formation, Reservation


class FormationListSerializer(serializers.ModelSerializer):
    available_seats   = serializers.IntegerField(read_only=True)
    fill_percentage   = serializers.IntegerField(read_only=True)
    is_full           = serializers.BooleanField(read_only=True)
    countdown_seconds = serializers.IntegerField(read_only=True)
    current_price     = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    level_display     = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Formation
        fields = [
            'id', 'title', 'slug', 'short_desc', 'image',
            'instructor_name', 'level', 'level_display',
            'location', 'is_online',
            'start_datetime', 'end_datetime', 'duration_label',
            'total_seats', 'available_seats', 'fill_percentage', 'is_full',
            'price', 'early_bird_price', 'early_bird_deadline', 'current_price',
            'countdown_seconds', 'status', 'is_featured',
        ]


class FormationDetailSerializer(FormationListSerializer):
    class Meta(FormationListSerializer.Meta):
        fields = FormationListSerializer.Meta.fields + [
            'description', 'program_details', 'what_you_learn', 'prerequisites',
        ]


class ReservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'formation', 'participant_name', 'participant_whatsapp',
            'participant_email', 'participant_note',
        ]

    def validate_formation(self, formation):
        if formation.is_full:
            raise serializers.ValidationError(
                "Cette formation est complète."
            )
        if formation.start_datetime <= timezone.now():
            raise serializers.ValidationError(
                "Les inscriptions pour cette formation sont closes."
            )
        if formation.status not in ('published', 'full'):
            raise serializers.ValidationError("Formation non disponible.")
        return formation

    def create(self, validated_data):
        formation = validated_data['formation']
        if formation.is_full:
            validated_data['status'] = Reservation.Status.WAITLIST
        return super().create(validated_data)


class ReservationReadSerializer(serializers.ModelSerializer):
    formation_title = serializers.CharField(source='formation.title', read_only=True)
    formation_date  = serializers.DateTimeField(source='formation.start_datetime', read_only=True)
    amount_to_pay   = serializers.DecimalField(
        source='formation.current_price', max_digits=10, decimal_places=0, read_only=True
    )
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    payment_info    = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            'id', 'reference', 'status', 'status_display',
            'formation', 'formation_title', 'formation_date',
            'participant_name', 'participant_whatsapp', 'participant_email',
            'amount_to_pay', 'amount_paid', 'payment_method',
            'payment_info', 'created_at',
        ]

    def get_payment_info(self, obj):
        from core.models import SiteSettings
        settings = SiteSettings.get()
        return {
            'momo_number': settings.momo_number,
            'momo_name':   settings.momo_name,
            'amount':      str(obj.formation.current_price),
            'reference':   obj.reference,
        }
