from rest_framework import serializers
from .models import QuoteRequest, PrintFile
from core.fields import AbsoluteUrlField


class PrintFileUploadSerializer(serializers.ModelSerializer):
    file = AbsoluteUrlField()

    class Meta:
        model = PrintFile
        fields = ['id', 'claim_token', 'file', 'original_filename', 'file_size_kb', 'description', 'uploaded_at']
        read_only_fields = ['claim_token', 'original_filename', 'file_size_kb', 'uploaded_at']

    def validate_file(self, value):
        # DRF n'exécute pas les validators de modèle sur les FileField :
        # on force la validation (extension + magic bytes + taille) ici.
        from django.core.exceptions import ValidationError as DjangoValidationError
        from .models import validate_print_file
        try:
            validate_print_file(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value


class PrintFileSerializer(serializers.ModelSerializer):
    file = AbsoluteUrlField(read_only=True)

    class Meta:
        model = PrintFile
        fields = ['id', 'file', 'original_filename', 'file_size_kb', 'description', 'uploaded_at']
        read_only_fields = ['original_filename', 'file_size_kb', 'uploaded_at']


class QuoteRequestSerializer(serializers.ModelSerializer):
    print_files = PrintFileSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.DictField(),
        write_only=True, required=False, default=list
    )
    whatsapp_notify_url = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = QuoteRequest
        fields = [
            'id', 'customer_name', 'customer_whatsapp', 'customer_email',
            'service_type', 'status', 'status_display',
            'event_date', 'event_location', 'event_description',
            'catering_details', 'print_details',
            'additional_note',
            'print_files', 'uploaded_files',
            'whatsapp_notify_url',
            'quote_amount', 'quote_message', 'quote_sent_at',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_whatsapp_notify_url(self, obj):
        from shop.notifications import quote_whatsapp_notify_url
        return quote_whatsapp_notify_url(obj)

    def validate(self, attrs):
        service_type = attrs.get('service_type')
        catering = attrs.get('catering_details', {})
        prints = attrs.get('print_details', {})
        if service_type in ('traiteur', 'both') and not catering.get('guests_count'):
            raise serializers.ValidationError(
                {"catering_details": "Le nombre de convives est requis pour un devis traiteur."}
            )
        if service_type in ('imprimerie', 'both') and not prints.get('print_type'):
            raise serializers.ValidationError(
                {"print_details": "Le type d'impression est requis pour un devis imprimerie."}
            )
        return attrs

    def validate_uploaded_files(self, value):
        ids = []
        for item in value:
            file_id = item.get('id')
            token = item.get('token')
            if file_id is None or token is None:
                raise serializers.ValidationError(
                    "Chaque fichier doit fournir 'id' et 'token'."
                )
            try:
                pf = PrintFile.objects.get(pk=file_id)
            except PrintFile.DoesNotExist:
                raise serializers.ValidationError(f"Fichier {file_id} introuvable.")
            if str(pf.claim_token) != str(token):
                raise serializers.ValidationError(f"Token invalide pour le fichier {file_id}.")
            if pf.quote_request_id is not None:
                raise serializers.ValidationError(
                    f"Fichier {file_id} déjà rattaché à un devis."
                )
            ids.append(file_id)
        return ids

    def create(self, validated_data):
        # Le statut et la réponse de devis ne sont modifiables que par l'admin (update)
        validated_data.pop('status', None)
        validated_data.pop('quote_amount', None)
        validated_data.pop('quote_message', None)
        validated_data.pop('quote_sent_at', None)
        file_ids = validated_data.pop('uploaded_files', [])
        quote = QuoteRequest.objects.create(**validated_data)
        if file_ids:
            PrintFile.objects.filter(pk__in=file_ids).update(quote_request=quote)
        return quote
