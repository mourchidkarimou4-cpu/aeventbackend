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


from .models import Newsletter

class NewsletterView(_APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        name  = request.data.get('name', '').strip()
        if not email:
            return Response({'error': 'Email requis.'}, status=400)
        obj, created = Newsletter.objects.get_or_create(email=email, defaults={'name': name})
        if not created:
            if not obj.is_active:
                obj.is_active = True
                obj.save()
                return Response({'message': 'Vous êtes de retour parmi nous !'})
            return Response({'message': 'Vous êtes déjà abonné !'})
        return Response({'message': 'Inscription réussie ! Merci de rejoindre A\'Events.'}, status=201)


class NewsletterListView(_APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        subs = Newsletter.objects.filter(is_active=True).order_by('-created_at')
        data = [{'id': s.id, 'email': s.email, 'name': s.name, 'created_at': s.created_at} for s in subs]
        return Response({'count': len(data), 'results': data})


from .models import AvisClient

class AvisView(_APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.AllowAny()]

    def get(self, request):
        avis = AvisClient.objects.filter(is_approved=True).order_by('-created_at')[:10]
        data = [{
            'id': a.id, 'name': a.name, 'note': a.note,
            'message': a.message, 'service': a.service,
            'created_at': a.created_at,
        } for a in avis]
        return Response(data)

    def post(self, request):
        name    = request.data.get('name', '').strip()
        message = request.data.get('message', '').strip()
        note    = int(request.data.get('note', 5))
        service = request.data.get('service', 'general')
        email   = request.data.get('email', '').strip()

        if not name or not message:
            return Response({'error': 'Nom et message sont obligatoires.'}, status=400)

        avis = AvisClient.objects.create(
            name=name, message=message, note=note,
            service=service, email=email, is_approved=False
        )
        return Response({'message': 'Merci pour votre avis ! Il sera publié après modération.'}, status=201)


class AvisAdminView(_APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        avis = AvisClient.objects.all().order_by('-created_at')
        data = [{
            'id': a.id, 'name': a.name, 'note': a.note,
            'message': a.message, 'service': a.service,
            'email': a.email, 'is_approved': a.is_approved,
            'created_at': a.created_at,
        } for a in avis]
        return Response(data)

    def patch(self, request, pk):
        try:
            avis = AvisClient.objects.get(pk=pk)
            avis.is_approved = request.data.get('is_approved', not avis.is_approved)
            avis.save()
            return Response({'is_approved': avis.is_approved})
        except AvisClient.DoesNotExist:
            return Response({'error': 'Avis introuvable.'}, status=404)

    def delete(self, request, pk):
        try:
            AvisClient.objects.get(pk=pk).delete()
            return Response(status=204)
        except AvisClient.DoesNotExist:
            return Response({'error': 'Avis introuvable.'}, status=404)
