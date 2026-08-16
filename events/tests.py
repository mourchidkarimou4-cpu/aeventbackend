from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import PrintFile, QuoteRequest


class PrintFileUploadTestCase(APITestCase):
    def make_pdf(self, name='maquette.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4 fake content', content_type='application/pdf')

    def test_upload_returns_claim_token(self):
        res = self.client.post('/api/events/upload-files/', {
            'files': self.make_pdf(),
        }, format='multipart')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data['uploaded']), 1)
        self.assertIn('claim_token', res.data['uploaded'][0])

    def test_upload_rejects_non_allowed_extension(self):
        res = self.client.post('/api/events/upload-files/', {
            'files': SimpleUploadedFile('virus.exe', b'x', content_type='application/octet-stream'),
        }, format='multipart')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['uploaded'], [])

    def test_upload_rejects_too_many_files(self):
        files = [self.make_pdf(f'f{i}.pdf') for i in range(6)]
        res = self.client.post('/api/events/upload-files/', {'files': files}, format='multipart')
        self.assertEqual(res.status_code, 400)


class QuoteRequestTestCase(APITestCase):
    def make_pdf(self):
        return SimpleUploadedFile('flyer.pdf', b'%PDF-1.4 content', content_type='application/pdf')

    def base_payload(self, **overrides):
        payload = {
            'customer_name': 'Nadia Hounkpe',
            'customer_whatsapp': '+22997777777',
            'service_type': 'imprimerie',
            'print_details': {'print_type': 'flyers', 'quantity': 500},
        }
        payload.update(overrides)
        return payload

    def test_quote_requires_print_type(self):
        res = self.client.post('/api/events/quotes/', self.base_payload(
            print_details={'quantity': 100}
        ), format='json')
        self.assertEqual(res.status_code, 400)

    def test_quote_attaches_uploaded_files(self):
        up = self.client.post('/api/events/upload-files/', {
            'files': self.make_pdf(),
        }, format='multipart')
        uploaded = up.data['uploaded'][0]

        res = self.client.post('/api/events/quotes/', self.base_payload(
            uploaded_files=[{'id': uploaded['id'], 'token': uploaded['claim_token']}]
        ), format='json')
        self.assertEqual(res.status_code, 201)
        quote = QuoteRequest.objects.get(pk=res.data['id'])
        self.assertEqual(quote.print_files.count(), 1)
        self.assertEqual(str(quote.print_files.first().claim_token), uploaded['claim_token'])

    def test_quote_rejects_wrong_token(self):
        up = self.client.post('/api/events/upload-files/', {
            'files': self.make_pdf(),
        }, format='multipart')
        uploaded = up.data['uploaded'][0]

        res = self.client.post('/api/events/quotes/', self.base_payload(
            uploaded_files=[{'id': uploaded['id'], 'token': 'wrong-token'}]
        ), format='json')
        self.assertEqual(res.status_code, 400)

    def test_quote_rejects_already_attached_file(self):
        up = self.client.post('/api/events/upload-files/', {
            'files': self.make_pdf(),
        }, format='multipart')
        uploaded = up.data['uploaded'][0]

        first = self.client.post('/api/events/quotes/', self.base_payload(
            uploaded_files=[{'id': uploaded['id'], 'token': uploaded['claim_token']}]
        ), format='json')
        self.assertEqual(first.status_code, 201)

        second = self.client.post('/api/events/quotes/', self.base_payload(
            customer_name='Autre Client',
            uploaded_files=[{'id': uploaded['id'], 'token': uploaded['claim_token']}]
        ), format='json')
        self.assertEqual(second.status_code, 400)
