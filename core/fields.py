from rest_framework import serializers


class AbsoluteUrlField(serializers.FileField):
    """Champ fichier dont la représentation est une URL absolue.

    Le frontend vit sur un autre hôte (Vite dev / CDN) : une URL relative
    (/media/...) pointerait vers l'hôte frontend et casserait les affichages.
    En stockage local (sans Cloudinary), on rend l'URL absolue via la requête.
    """

    def to_representation(self, value):
        if not value:
            return None
        url = value.url
        if url.startswith(('http://', 'https://')):
            return url
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url
