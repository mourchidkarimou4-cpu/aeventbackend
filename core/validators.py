"""Validation par signature binaire (magic bytes) des fichiers uploadés.

Le content_type déclaré par le client est falsifiable : on inspecte l'en-tête
du fichier lui-même avant tout stockage / upload Cloudinary.
"""

READ_LEN = 16

IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp'}
DOCUMENT_MIMES = {'application/pdf', 'image/jpeg', 'image/png'}


def sniff_mime(file):
    """Retourne le type MIME réel détecté (magic bytes) ou None si inconnu.

    Restaure la position de lecture du fichier après l'inspection.
    """
    pos = file.tell()
    head = file.read(READ_LEN)
    file.seek(pos)

    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head.startswith(b'GIF87a') or head.startswith(b'GIF89a'):
        return 'image/gif'
    if head.startswith(b'RIFF') and head[8:12] == b'WEBP':
        return 'image/webp'
    if head.startswith(b'%PDF'):
        return 'application/pdf'
    return None


def is_uploaded_file(value):
    """True si `value` est un fichier uploadé (et non une URL / une chaîne)."""
    return hasattr(value, 'read') and hasattr(value, 'size')


def validate_magic(file, allowed_mimes, label):
    """Lève une ValidationError si le fichier n'a pas une signature autorisée."""
    from django.core.exceptions import ValidationError

    detected = sniff_mime(file)
    if detected is None or detected not in allowed_mimes:
        raise ValidationError(
            f"{label} : contenu non reconnu. Formats acceptés : "
            f"{', '.join(sorted(allowed_mimes))}."
        )


def drf_validate_magic(value, allowed_mimes, label):
    """Validateur DRF réutilisable pour un champ fichier/image.

    Ignore les valeurs non-fichier (ex. URL Cloudinary passée en chaîne).
    """
    from rest_framework import serializers

    if not is_uploaded_file(value):
        return
    detected = sniff_mime(value)
    if detected is None or detected not in allowed_mimes:
        raise serializers.ValidationError(
            f"{label} : contenu non reconnu. Formats acceptés : "
            f"{', '.join(sorted(allowed_mimes))}."
        )
