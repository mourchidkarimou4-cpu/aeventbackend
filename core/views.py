from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from .models import SiteSettings
from .serializers import SiteSettingsSerializer
from .stats import DashboardStatsView


class SiteSettingsView(APIView):

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        settings = SiteSettings.get()
        return Response(SiteSettingsSerializer(settings).data)

    def patch(self, request):
        settings = SiteSettings.get()
        serializer = SiteSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


from rest_framework import viewsets, parsers, permissions
from .models import GaleriePhoto
from .serializers import GaleriePhotoSerializer

class GaleriePhotoViewSet(viewsets.ModelViewSet):
    queryset = GaleriePhoto.objects.filter(is_active=True).order_by('order', '-created_at')
    serializer_class = GaleriePhotoSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


from rest_framework.views import APIView as _APIView

class ChangePasswordView(_APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password):
            return Response({'detail': 'Mot de passe actuel incorrect.'}, status=400)

        if len(new_password) < 8:
            return Response({'detail': 'Le mot de passe doit contenir au moins 8 caractères.'}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Mot de passe modifié avec succès.'})
