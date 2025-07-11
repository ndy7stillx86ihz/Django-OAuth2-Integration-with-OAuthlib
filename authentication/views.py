import secrets

import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView
from oauthlib.oauth2 import WebApplicationClient

from core import settings


def oauth_login(request):
    client_id = settings.OAUTH_CLIENT_ID

    client = WebApplicationClient(client_id)

    authorization_url = settings.OAUTH_AUTHORIZATION_URI

    # Store state info in session
    request.session['state'] = secrets.token_urlsafe(16)

    url = client.prepare_request_uri(
        authorization_url,
        redirect_uri=settings.OAUTH_CALLBACK_URL,
        scope=settings.OAUTH_SCOPES,
        state=request.session['state']
    )

    return HttpResponseRedirect(url)


class CallbackView(TemplateView):

    def get(self, request, *args, **kwargs):

        # Retrieve these data from the URL
        data = self.request.GET
        code = data['code']
        state = data['state']

        # For security purposes, verify that the
        # state information is the same as was passed
        # to github_login()
        if self.request.session['state'] != state:
            messages.add_message(
                self.request,
                messages.ERROR,
                "State information mismatch!"
            )
            return HttpResponseRedirect(reverse('demo:welcome'))
        else:
            del self.request.session['state']

        # fetch the access token from GitHub's API at token_url
        token_url = settings.OAUTH_TOKEN_URI
        client_id = settings.OAUTH_CLIENT_ID
        client_secret = settings.OAUTH_CLIENT_SECRET

        # Create a Web Applicantion Client from oauthlib
        client = WebApplicationClient(client_id)

        # Prepare body for request
        data = client.prepare_request_body(
            code=code,
            redirect_uri=settings.OAUTH_CALLBACK_URL,
            client_id=client_id,
            client_secret=client_secret
        )

        # Post a request at GitHub's token_url
        # Returns requests.Response object
        response = requests.post(
            token_url,
            headers={
                "content-type": "application/x-www-form-urlencoded"
            },
            data=data
        )

        """
        Parse the unicode content of the response object
        Returns a dictionary stored in client.token
        {
          'access_token': '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',
          'scope': ['read:user'],
          'token_type': 'bearer'
        }
        """
        client.parse_request_body_response(response.text)

        # Prepare an Authorization header for GET request using the 'access_token' value
        # using GitHub's official API format
        header = {'Authorization': f'Bearer {client.token["access_token"]}'}

        # Retrieve GitHub profile data
        # Send a GET request
        # Returns requests.Response object
        response = requests.get(settings.OAUTH_USERINFO_URI, headers=header)

        # Store profile data in JSON
        json_dict = response.json()

        # save the user profile in a session
        self.request.session['profile'] = json_dict

        # retrieve or create a Django User for this profile
        try:
            user = User.objects.get(username=json_dict['username'])

            messages.add_message(self.request, messages.DEBUG,
                                 "User %s already exists, Authenticated? %s" % (user.username, user.is_authenticated))

            # remember to log the user into the system
            login(self.request, user)

        except:
            # create a Django User for this login
            user = User.objects.create_user(json_dict['username'], json_dict['email'])

            messages.add_message(self.request, messages.DEBUG,
                                 "User %s is created, Authenticated %s?" % (user.username, user.is_authenticated))

            # remember to log the user into the system
            login(self.request, user)

        # Redirect response to hide the callback url in browser
        return HttpResponseRedirect(reverse('demo:welcome'))


def logout_request(request):
    logout(request)
    messages.add_message(request, messages.SUCCESS, "You are successfully logged out")
    return HttpResponseRedirect(reverse('demo:home'))