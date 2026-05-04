from rest_framework import serializers
from .models import QuoteRequest, PrintFile


class PrintFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrintFile
        fields = ['id', 'file', 'original_filename', 'file_size_kb', 'description', 'uploaded_at']
        read_only_fields = ['original_filename', 'file_size_kb', 'uploaded_at']


class QuoteRequestSerializer(serializers.ModelSerializer):
    print_files = PrintFileSerializer(many=True, read_only=True)
    uploaded_file_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True, required=False, default=list
    )

    class Meta:
        model = QuoteRequest
        fields = [
            'id', 'customer_name', 'customer_whatsapp', 'customer_email',
            'service_type', 'status',
            'event_date', 'event_location', 'event_description',
            'catering_details', 'print_details',
            'additional_note',
            'print_files', 'uploaded_file_ids',
            'created_at',
        ]
        read_only_fields = ['status', 'created_at']

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

    def create(self, validated_data):
        file_ids = validated_data.pop('uploaded_file_ids', [])
        quote = QuoteRequest.objects.create(**validated_data)
        if file_ids:
            PrintFile.objects.filter(
                pk__in=file_ids, quote_request__isnull=True
            ).update(quote_request=quote)
        return quote
