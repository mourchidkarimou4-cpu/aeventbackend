from rest_framework import serializers
from .models import MessageChat


class MessageChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageChat
        fields = ['id', 'session_id', 'client_nom', 'client_wa', 'contenu', 'is_admin', 'is_read', 'created_at']
        read_only_fields = ['is_admin', 'is_read', 'created_at']

    def validate_contenu(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le message est vide.")
        if len(value) > 2000:
            raise serializers.ValidationError("Message trop long (2000 caractères max).")
        return value

    def validate_client_nom(self, value):
        if value and len(value) > 100:
            raise serializers.ValidationError("Nom trop long (100 caractères max).")
        return value


class MessageChatPublicSerializer(serializers.ModelSerializer):
    """Sérialiseur public : n'expose pas les coordonnées du client."""
    class Meta:
        model = MessageChat
        fields = ['id', 'session_id', 'contenu', 'is_admin', 'is_read', 'created_at']
        read_only_fields = fields
