from rest_framework import viewsets
from .models import Keyword, GlobalConfig
from .serializers import KeywordSerializer, GlobalConfigSerializer

class KeywordViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar las palabras clave.
    """
    queryset = Keyword.objects.all().order_by('-created_at')
    serializer_class = KeywordSerializer

class GlobalConfigViewSet(viewsets.ModelViewSet):
    """
    API endpoint para la configuración global.
    Normalmente solo habrá un registro de configuración.
    """
    queryset = GlobalConfig.objects.all()
    serializer_class = GlobalConfigSerializer
