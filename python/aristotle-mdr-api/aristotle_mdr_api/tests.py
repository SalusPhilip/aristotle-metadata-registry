from django.test import TestCase, Client, override_settings
from django.urls import reverse

from aristotle_mdr.tests import utils

import json

@override_settings(SECURE_SSL_REDIRECT=False)
class TokenTestCase(utils.LoggedInViewPages, TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client()

    def post_token_create(self, name, perms):

        postdata = {'name': name, 'perm_json': json.dumps(perms)}
        response = self.client.post(reverse('token_create'), postdata)
        return response

    def get_token(self, name, perms):

        response = self.post_token_create(name, perms)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('key' in response.context.keys())
        return response.context['key']

    def test_create_token(self):

        response = self.client.get(reverse('token_create'))
        self.assertEqual(response.status_code, 302)

        self.login_viewer()

        response = self.client.get(reverse('token_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aristotle_mdr_api/token_create.html')

        perms = {
            'metadata': {
                'read': True,
                'write': False
            },
            'search': {
                'read': True,
                'write': False
            },
            'workgroup': {
                'read': True,
                'write': False
            },
            'ra': {
                'read': True,
                'write': False
            }
        }

        token = self.get_token('MyToken', perms)
