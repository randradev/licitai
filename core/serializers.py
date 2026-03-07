from rest_framework import serializers
from .models import Keyword, GlobalConfig

class KeywordSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Keyword.
    """
    class Meta:
        model = Keyword
        fields = ['id', 'term', 'is_negative', 'created_at']
        read_only_fields = ['id', 'created_at']

class GlobalConfigSerializer(serializers.ModelSerializer):
    """
    Serializador para la configuración global del sistema.
    """
    class Meta:
        model = GlobalConfig
        fields = ['id', 'api_ticket_encrypted', 'credits_balance']
        read_only_fields = ['id']
