from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from catalogue.models import Record, Application


class RecordAdminTestCase(TestCase):

    def setUp(self):
        # Generate a test user for endpoint responses.
        self.testuser = User.objects.create_user(
            username='testuser', email='testuser@dbca.wa.gov.au.com', password='pass', is_staff=True, is_superuser=True)
        # Log in testuser by default.
        self.client.login(username='testuser', password='pass')
        # Generate some Record objects.
        mixer.cycle(8).blend(Record, title=mixer.RANDOM)

    def test_changelist(self):
        """Test the Record admin changelist view
        """
        url = reverse('admin:catalogue_record_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change(self):
        """Test the Record admin change form
        """
        record = Record.objects.first()
        url = reverse('admin:catalogue_record_change', args=(record.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
