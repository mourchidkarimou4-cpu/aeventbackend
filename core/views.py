from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from .models import SiteSettings
from .serializers import SiteSettingsSerializer
from .validators import sniff_mime, IMAGE_MIMES, DOCUMENT_MIMES


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
    serializer_class = GaleriePhotoSerializer
    queryset = GaleriePhoto.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        qs = GaleriePhoto.objects.all().order_by('order', '-created_at')
        if self.request.user and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True)

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


ALLOWED_IMAGE_TYPES = IMAGE_MIMES
ALLOWED_DOSSIER_TYPES = DOCUMENT_MIMES
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_DOSSIER_SIZE = 5 * 1024 * 1024


MIME_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
}


def _save_local(file, folder, request):
    """Stockage local (MEDIA_ROOT) en l'absence de Cloudinary.

    Retourne une URL absolue : le frontend est sur un autre hôte et ne peut
    pas afficher une URL relative (/media/...) pointant vers l'hôte frontend.
    """
    from uuid import uuid4
    from django.core.files.storage import default_storage

    ext = MIME_EXT.get(sniff_mime(file))
    name = f"{folder.strip('/')}/{uuid4().hex}{ext or ''}"
    saved_name = default_storage.save(name, file)
    url = default_storage.url(saved_name)
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


def _upload_to_cloudinary(file, folder, resource_type='image', request=None):
    """Persiste un upload : Cloudinary si configuré, sinon stockage local."""
    if getattr(settings, 'CLOUDINARY_CONFIGURED', False):
        from cloudinary import uploader as cloudinary_uploader
        result = cloudinary_uploader.upload(
            file, folder=folder, resource_type=resource_type
        )
        return result['secure_url']
    return _save_local(file, folder, request)


class ImageUploadView(APIView):
    """Upload d'image réservé aux admins (signé côté serveur)."""
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_scope = 'file_upload'

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'Aucun fichier fourni.'}, status=400)
        # Vérification par magic bytes : le content_type client est falsifiable
        if sniff_mime(file) not in ALLOWED_IMAGE_TYPES:
            return Response({'error': 'Format non autorisé (JPG, PNG, WEBP).'}, status=400)
        if file.size > MAX_IMAGE_SIZE:
            return Response({'error': 'Image trop volumineuse (10 Mo max).'}, status=400)

        folder = request.data.get('folder', 'ams').strip('/') or 'ams'
        try:
            secure_url = _upload_to_cloudinary(file, folder, request=request)
        except Exception:
            return Response({'error': 'Échec de l’upload.'}, status=500)
        return Response({'secure_url': secure_url})


class DossierUploadView(APIView):
    """Upload public des pièces de candidature (academy), signé côté serveur."""
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_scope = 'file_upload'

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'Aucun fichier fourni.'}, status=400)
        # Vérification par magic bytes : le content_type client est falsifiable
        if sniff_mime(file) not in ALLOWED_DOSSIER_TYPES:
            return Response({'error': 'Format non autorisé (JPG, PNG, PDF).'}, status=400)
        if file.size > MAX_DOSSIER_SIZE:
            return Response({'error': 'Fichier trop volumineux (5 Mo max).'}, status=400)

        try:
            secure_url = _upload_to_cloudinary(
                file, 'ams/dossiers', resource_type='auto', request=request
            )
        except Exception:
            return Response({'error': 'Échec de l’upload.'}, status=500)
        return Response({'secure_url': secure_url})


class ChangePasswordView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password or ''):
            return Response({'detail': 'Mot de passe actuel incorrect.'}, status=400)

        if not new_password or len(new_password) < 8:
            return Response({'detail': 'Le mot de passe doit contenir au moins 8 caractères.'}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Mot de passe modifié avec succès.'})


from .models import Newsletter

class NewsletterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'newsletter'

    def post(self, request):
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        email = request.data.get('email', '').strip().lower()
        name  = (request.data.get('name', '').strip() or '')[:100]
        if not email:
            return Response({'error': 'Email requis.'}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return Response({'error': 'Adresse email invalide.'}, status=400)
        obj, created = Newsletter.objects.get_or_create(email=email, defaults={'name': name})
        if not created:
            if not obj.is_active:
                obj.is_active = True
                obj.save()
                return Response({'message': 'Vous êtes de retour parmi nous !'})
            return Response({'message': 'Vous êtes déjà abonné !'})
        return Response({'message': 'Inscription réussie ! Merci de rejoindre A\'Events.'}, status=201)


class NewsletterListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        subs = Newsletter.objects.filter(is_active=True).order_by('-created_at')
        data = [{'id': s.id, 'email': s.email, 'name': s.name, 'created_at': s.created_at} for s in subs]
        return Response({'count': len(data), 'results': data})


from .models import AvisClient

class AvisView(APIView):
    permission_classes = [AllowAny]

    def get_throttles(self):
        if self.request.method == 'POST':
            self.throttle_scope = 'avis'
            from rest_framework.throttling import ScopedRateThrottle
            return [ScopedRateThrottle()]
        return []

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
        service = request.data.get('service', 'general').strip()
        email   = request.data.get('email', '').strip()

        if not name or not message:
            return Response({'error': 'Nom et message sont obligatoires.'}, status=400)

        valid_services = [c[0] for c in AvisClient._meta.get_field('service').choices]
        if service not in valid_services:
            return Response({'error': 'Service invalide.'}, status=400)

        try:
            note = int(request.data.get('note', 5))
        except (TypeError, ValueError):
            return Response({'error': 'La note doit être un nombre.'}, status=400)
        if not 1 <= note <= 5:
            return Response({'error': 'La note doit être comprise entre 1 et 5.'}, status=400)

        avis = AvisClient.objects.create(
            name=name, message=message, note=note,
            service=service, email=email, is_approved=False
        )
        return Response({'message': 'Merci pour votre avis ! Il sera publié après modération.'}, status=201)


class AvisAdminView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk=None):
        avis = AvisClient.objects.all().order_by('-created_at')
        if pk is not None:
            try:
                a = avis.get(pk=pk)
            except AvisClient.DoesNotExist:
                return Response({'error': 'Avis introuvable.'}, status=404)
            return Response({
                'id': a.id, 'name': a.name, 'note': a.note,
                'message': a.message, 'service': a.service,
                'email': a.email, 'is_approved': a.is_approved,
                'created_at': a.created_at,
            })
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
            raw = request.data.get('is_approved')
            if raw is None or raw == '':
                is_approved = not avis.is_approved
            elif isinstance(raw, str):
                is_approved = raw.strip().lower() in ('1', 'true', 'yes', 'on')
            else:
                is_approved = bool(raw)
            avis.is_approved = is_approved
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


from .models import Temoignage
from .serializers import TemoignageSerializer

class TemoignageViewSet(viewsets.ModelViewSet):
    serializer_class = TemoignageSerializer
    queryset = Temoignage.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        qs = Temoignage.objects.all().order_by('order', '-created_at')
        if self.request.user and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True)

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


from django.contrib.auth.models import User
from .models import AdminProfile

class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    @staticmethod
    def _is_super_admin(user):
        profile = getattr(user, 'admin_profile', None)
        return bool(profile and profile.role == 'super_admin') or bool(user.is_superuser)

    def get(self, request):
        users = User.objects.filter(is_staff=True).select_related('admin_profile')
        data = []
        for u in users:
            profile = getattr(u, 'admin_profile', None)
            data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'is_active': u.is_active,
                'date_joined': u.date_joined,
                'role': profile.role if profile else 'super_admin',
                'phone': profile.phone if profile else '',
            })
        return Response(data)

    def post(self, request):
        if not self._is_super_admin(request.user):
            return Response(
                {'error': 'Seul un super administrateur peut créer des comptes.'}, status=403)

        username = request.data.get('username')
        email = request.data.get('email', '')
        password = request.data.get('password')
        role = request.data.get('role', 'viewer')
        phone = request.data.get('phone', '')

        if not username or not password:
            return Response({'error': 'Username et password requis.'}, status=400)

        valid_roles = [r[0] for r in AdminProfile.ROLES]
        if role not in valid_roles:
            return Response({'error': 'Rôle invalide.'}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Ce username existe déjà.'}, status=400)

        user = User.objects.create_user(
            username=username, email=email, password=password,
            is_staff=True
        )
        AdminProfile.objects.create(user=user, role=role, phone=phone)
        return Response({
            'id': user.id, 'username': user.username,
            'email': user.email, 'role': role,
        }, status=201)

    def delete(self, request):
        if not self._is_super_admin(request.user):
            return Response(
                {'error': 'Seul un super administrateur peut supprimer des comptes.'}, status=403)
        user_id = request.data.get('user_id')
        if str(request.user.id) == str(user_id):
            return Response({'error': 'Vous ne pouvez pas supprimer votre propre compte.'}, status=400)
        try:
            user = User.objects.get(id=user_id, is_staff=True)
            user.delete()
            return Response(status=204)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=404)


class AuthMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        profile = getattr(user, 'admin_profile', None)

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'role': profile.role if profile else 'super_admin',
        })


from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import SimpleRateThrottle
from django.contrib.auth import get_user_model
import hmac
import os


class AdminResetThrottle(SimpleRateThrottle):
    scope = 'admin_reset'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AdminResetThrottle])
def reset_admin_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    secret = os.environ.get('ADMIN_RESET_TOKEN')

    if not secret:
        return Response({'error': 'Non configuré.'}, status=503)
    if not token or not hmac.compare_digest(str(token), secret):
        return Response({'error': 'Token invalide.'}, status=403)
    if not new_password or len(new_password) < 8:
        return Response({'error': 'Mot de passe trop court (8 caractères min).'}, status=400)

    User = get_user_model()
    try:
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            return Response({'error': 'Aucun superuser trouvé.'}, status=404)
        admin.set_password(new_password)
        admin.save(update_fields=['password'])
        return Response({'success': 'Mot de passe réinitialisé.'})
    except Exception:
        return Response({'error': 'Erreur interne.'}, status=500)


class LoginThrottle(SimpleRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


# ── JWT en cookies HttpOnly (login / refresh / logout) ──
from django.conf import settings
from rest_framework import serializers, status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 jours, aligné sur REFRESH_TOKEN_LIFETIME


def _set_jwt_cookies(response, access, refresh=None):
    """Pose les cookies HttpOnly. Retourne la réponse (chaînable)."""
    response.set_cookie(
        settings.JWT_ACCESS_COOKIE,
        access,
        max_age=None,  # cookie de session : recréé par la rotation du refresh
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite='Lax',
        path='/',
    )
    if refresh:
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE,
            refresh,
            max_age=REFRESH_COOKIE_MAX_AGE,
            httponly=True,
            secure=settings.JWT_COOKIE_SECURE,
            samesite='Lax',
            path='/',
        )
    return response


def _clear_jwt_cookies(response):
    for name in (settings.JWT_ACCESS_COOKIE, settings.JWT_REFRESH_COOKIE):
        response.delete_cookie(name, path='/')
    return response


class CookieTokenObtainPairView(TokenObtainPairView):
    """Login : JWT stocké en cookies HttpOnly (plus aucun token en JS/localStorage)."""
    throttle_classes = [LoginThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            _set_jwt_cookies(
                response,
                access=response.data.get('access'),
                refresh=response.data.get('refresh'),
            )
        return response


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    """Lit le refresh token dans le cookie HttpOnly au lieu du corps de la requête."""
    refresh = serializers.CharField(required=False)

    def validate(self, attrs):
        attrs['refresh'] = self.context['request'].COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not attrs['refresh']:
            raise InvalidToken('Refresh token absent.')
        return super().validate(attrs)


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh : fait tourner access + refresh depuis les cookies HttpOnly."""
    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            _set_jwt_cookies(
                response,
                access=response.data.get('access'),
                refresh=response.data.get('refresh'),
            )
        return response


class LogoutView(APIView):
    """Déconnexion : blackliste le refresh token et supprime les cookies."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass
        response = Response({'success': 'Déconnecté.'})
        return _clear_jwt_cookies(response)
