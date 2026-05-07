from rest_framework import serializers
from .models import MessageChat

class MessageChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageChat
        fields = '__all__'
