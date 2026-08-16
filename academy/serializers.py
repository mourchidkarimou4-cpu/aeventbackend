from rest_framework import serializers
from django.utils import timezone
from core.fields import AbsoluteUrlField
from .models import Formation, Reservation


class FormationListSerializer(serializers.ModelSerializer):
    available_seats   = serializers.IntegerField(read_only=True)
    fill_percentage   = serializers.IntegerField(read_only=True)
    is_full           = serializers.BooleanField(read_only=True)
    countdown_seconds = serializers.IntegerField(read_only=True)
    current_price     = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    level_display     = serializers.CharField(source='get_level_display', read_only=True)
    image             = AbsoluteUrlField(required=False, allow_null=True)

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
        if formation.start_datetime <= timezone.now():
            raise serializers.ValidationError(
                "Les inscriptions pour cette formation sont closes."
            )
        if formation.status not in ('published', 'full'):
            raise serializers.ValidationError("Formation non disponible.")
        return formation


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


class FormationAdminSerializer(serializers.ModelSerializer):
    available_seats   = serializers.IntegerField(read_only=True)
    fill_percentage   = serializers.IntegerField(read_only=True)
    current_price     = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    reservations_count = serializers.SerializerMethodField()

    class Meta:
        model = Formation
        fields = '__all__'

    def get_reservations_count(self, obj):
        if obj.reservations.prefetched_objects:
            return len(obj.reservations.all())
        return obj.reservations.count()


from .models import FormationPresentielle, DossierCandidature
from core.validators import drf_validate_magic, IMAGE_MIMES, DOCUMENT_MIMES


def _absolute_url(request, value):
    if not value:
        return None
    if value.startswith(('http://', 'https://')):
        return value
    if request:
        return request.build_absolute_uri(value)
    return value

class FormationPresentiellSerializer(serializers.ModelSerializer):
    inscription_ouverte = serializers.ReadOnlyField()
    affiche_url = serializers.SerializerMethodField()
    places_inscrites = serializers.SerializerMethodField()

    class Meta:
        model = FormationPresentielle
        fields = '__all__'

    def get_affiche_url(self, obj):
        return _absolute_url(self.context.get('request'), obj.affiche)

    def get_places_inscrites(self, obj):
        val = getattr(obj, '_places_inscrites', None)
        if val is None:
            val = obj.dossiers.count()
        return val

    def validate_affiche(self, value):
        drf_validate_magic(value, IMAGE_MIMES, 'Affiche')
        return value


class DossierCandidatureSerializer(serializers.ModelSerializer):
    formation_titre = serializers.CharField(source='formation.titre', read_only=True)
    piece_identite_url = serializers.SerializerMethodField()
    photo_identite_url = serializers.SerializerMethodField()

    class Meta:
        model = DossierCandidature
        fields = '__all__'
        read_only_fields = ['statut', 'created_at']

    def get_piece_identite_url(self, obj):
        return _absolute_url(self.context.get('request'), obj.piece_identite)

    def get_photo_identite_url(self, obj):
        return _absolute_url(self.context.get('request'), obj.photo_identite)

    def validate_piece_identite(self, value):
        drf_validate_magic(value, DOCUMENT_MIMES, 'Pièce d\'identité')
        return value

    def validate_photo_identite(self, value):
        drf_validate_magic(value, IMAGE_MIMES, 'Photo d\'identité')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method == 'POST':
            formation = attrs.get('formation')
            telephone = attrs.get('telephone')
            if formation is None:
                raise serializers.ValidationError('Formation requise.')
            if not formation.is_active:
                raise serializers.ValidationError('Cette formation n\'est plus disponible.')
            if not formation.inscription_ouverte:
                raise serializers.ValidationError(
                    'Les inscriptions pour cette formation sont clôturées.'
                )
            if formation.nb_places is not None:
                existing = DossierCandidature.objects.filter(formation=formation).count()
                if existing >= formation.nb_places:
                    raise serializers.ValidationError('Cette formation est complète.')
            if telephone and DossierCandidature.objects.filter(
                formation=formation, telephone=telephone
            ).exists():
                raise serializers.ValidationError({
                    'telephone': 'Un dossier existe déjà pour ce numéro sur cette formation.'
                })
        return attrs
