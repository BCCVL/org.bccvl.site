#
import json
import logging
from urlparse import urljoin
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import NotFound, BadRequest, Unauthorized
from zope.publisher.interfaces import IPublishTraverse
from zope.security import checkPermission
from .interfaces import IOAuth1Settings, IOAuth2Settings


LOG = logging.getLogger(__name__)

def check_authenticated(func):
    def check(*args, **kw):
        if api.user.is_anonymous():
            raise Unauthorized()
        return func(*args, **kw)
    return check

class OAuthBaseView(BrowserView):

    _skey = "{0}_oauth_token"
    _session = None
    _property = "{0}_oauth_token"
    config = None

    def __init__(self, context, request, config):
        super(OAuthBaseView, self).__init__(context, request)
        self._property = self._property.format(config.id)
        self._skey = self._skey.format(config.id)
        self.config = config

    @property
    def session(self):
        # get current session
        if not self._session:
            sdm = getToolByName(self.context, 'session_data_manager')
            self._session = sdm.getSessionData(create=True)
        return self._session

    def getToken(self):
        # get token for current user
        member = api.user.get_current()
        token = member.getProperty(self._property, "")
        #LOG.info('Found stored token: %s', token)
        if token:
            token = json.loads(token)
        return token

    def setToken(self, token):
        # permanently store token for user.
        # creates new memberdata property if necesarry
        member = api.user.get_current()
        # CMF WAY? ... prepare property sheet... need to do this only once?
        pmd = getToolByName(self.context, 'portal_memberdata')
        if not pmd.hasProperty(self._property):
            LOG.info('added new token property to member data tool')
            pmd.manage_addProperty(id=self._property, value="", type="string")

        # Would there be a PAS way as well?
        # acl_users = getToolByName(self.context, 'acl_users')
        # property_plugins = acl_users.plugins.listPlugins(IPropertiesPlugin)
        member.setProperties({self._property: json.dumps(token)})

    def hasToken(self):
        try:
            return bool(self.getToken())
        except Exception:
            return False

    def cleartoken(self):
        # get token for current user
        member = api.user.get_current()
        member.setProperty(self._property, "")
        return_url = self.request.get('HTTP_REFERER')
        self.request.response.redirect(return_url)


class OAuth2View(OAuthBaseView):

    def oauth_session(self, token=None, state=None):
        from requests_oauthlib import OAuth2Session
        if not token:
            token = {}

        #scope = ["profile", "email"]
        scope = ['https://www.googleapis.com/auth/userinfo.email',
                 'https://www.googleapis.com/auth/userinfo.profile']

        redirect_url = self.config.redirect_url
        if not redirect_url:
            redirect_url = urljoin(self.request.getURL(), 'callback')

        oauth = OAuth2Session(self.config.client_id, state=state,
                              redirect_uri=redirect_url, token=token,
                              auto_refresh_kwargs={'client_id': self.config.client_id,
                                                   'client_secret': self.config.client_secret},
                              auto_refresh_url=self.config.refresh_url,
                              token_updater=self.setToken,
                              scope=scope)
        return oauth

    @check_authenticated
    def authorize(self, access_type='offline', approval_prompt='force'):
        # redirect to external service authorisation page
        oauth = self.oauth_session()
        authorization_url, state = oauth.authorization_url(
            self.config.authorization_url,
            # access_type and approval_prompt are Google specific extra
            # parameters.
            access_type=access_type, approval_prompt=approval_prompt)
        # state ... roundtripped by oauth, can be used to verify response
        return_url = self.request.get('HTTP_REFERER')
        self.session[self._skey] = (state, return_url)
        # redirect to auth url?
        self.request.response.redirect(authorization_url)
        # TODO: what about failures here? return success/failure

    def is_callback(self):
        # check if request is a authorize "callback"
        return (self.config.authorization_url in self.request.get('HTTP_REFERER')
                and 'code' in self.request.form
                and 'state' in self.request.form)

    @check_authenticated
    def callback(self, state=None, return_url=None):
        if not self.is_callback():
            # TODO: maybe rais some other error here?
            raise NotFound(self.context, 'callback', self.request)
        # get current state to verify callback
        state, return_url = self.session.get(self._skey)
        # verify oauth callback
        oauth = self.oauth_session(state=state)
        # TODO: there should be a better way to get the full request url
        authorization_response = self.request.getURL() + '?' + self.request['QUERY_STRING']
        # the request must have some auth_response somewhere?
        # NOTE: since oauthlib 0.7.2 which correctly compares scope
        #       we need export OAUTHLIB_RELAX_TOKEN_SCOPE=1 or catch the Warning
        #       otherwise google login won't work
        # We no longer need 'state' after we have parsed the response url
        token = oauth.fetch_token(
            self.config.token_url,
            authorization_response=authorization_response,
            # Google specific extra parameter used for client
            # authentication
            client_secret=self.config.client_secret)
        # store token and clean up session
        if self.session.has_key(self._skey):
            del self.session[self._skey]
        self.setToken(token)
        # Do another redirect to clean up the url
        self.request.response.redirect(return_url or self.request.getURL())

    @check_authenticated
    def accesstoken(self):
        # FIXME: this is a quick workaround, user parameter should not be here
        if checkPermission('cmf.ManagePortal', self.context):
            # we are admin ... check if user is set
            username = self.request.form.get('user')
            member = api.user.get(username=username)
            access_token = member.getProperty(self._property, "")
            if access_token:
                access_token = json.loads(token)
        else:
            access_token = self.getToken()
        # return full access token for current user
        self.request.response['CONTENT-TYPE'] = 'application/json'
        return json.dumps(access_token)

    @check_authenticated
    def clienttoken(self):
        # only admin can fetch client token
        if not checkPermission('cmf.ManagePortal', self.context):
            raise Unauthorized()
        self.request.response['CONTENT-TYPE'] = 'application/json'
        return json.dumps({
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_url,
            'auto_refresh_kwargs': {
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret,
            },
            'auto_refresh_url': self.config.refresh_url
        })


    def validate(self):
        """Validate a token with the OAuth provider Google.
        """
        # TODO: OAuth2Session has attribute .authorized ... it only checks for presence of various tokens, but should be a good indicator of successfull authorisation
        token = self.getToken()
        try:
            # Defined at https://developers.google.com/accounts/docs/OAuth2LoginV1#validatingtoken
            validate_url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?'
                            'access_token=%s' % token['access_token'])
            # No OAuth2Session is needed, just a plain GET request
            import requests
            result = requests.get(validate_url)
            # TODO: return something more useful
            return True
        except Exception as e:
            LOG.info('OAuth validate failed: %s', e)
            return False

    def refresh(self):
        """Refreshing an OAuth 2 token using a refresh token.
        """
        token = self.getToken()
        extra = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
        }

        oauth = self.oath_session(token)
        new_token = oauth.refresh_token(self.config.refresh_url, **extra)
        return new_token

    # GOOGLE specific methods
    def userinfo(self):
        # fetch some info about our oauth connection and render them in template
        token = self.getToken()
        google = self.oauth_session(token=token)
        userinfo_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        # TODO: may throw requests ConnectionError in: requests.adapters:415
        # TODO: this returns the requests response object.. shall we retrun somethin else?
        result = google.get(userinfo_url)
        return result.text


class OAuth1View(OAuthBaseView):

    def oauth_session(self, token=None, state=None):
        from requests_oauthlib import OAuth1Session
        if not token:
            # token should contain access token if available
            token = {}

        redirect_url = self.config.redirect_url
        if not redirect_url:
            redirect_url = urljoin(self.request.getURL(), 'callback')

        # TODO: for ourselves we need to put static token key into resource_owner_xx
        oauth = OAuth1Session(client_key=self.config.client_key,
                              client_secret=self.config.client_secret,
                              resource_owner_key=token.get('oauth_token'),
                              resource_owner_secret=token.get('oauth_token_secret'),
                              verifier=token.get('oauth_verifier'),
                              callback_uri=redirect_url,
                              signature_type='auth_header')
        return oauth

    @check_authenticated
    def authorize(self):
        # redirect to external service authorisation page
        oauth = self.oauth_session()
        # get a request token for ourselves
        request_token = oauth.fetch_request_token(self.config.request_url)
        # get the authorization url and redirect user to it
        authorization_url = oauth.authorization_url(self.config.authorization_url)
        # state ... roundtripped by oauth, can be used to verify response
        return_url = self.request.get("HTTP_REFERER")
        self.session[self._skey] = (request_token, return_url)
        # redirect to auth url?
        self.request.response.redirect(authorization_url)
        # TODO: return something about success / failure?

    def is_callback(self):
        return ('oauth_verifier' in self.request.form
                and 'oauth_token' in self.request.form
                and self.config.oauth_url in self.request.environ['HTTP_REFERER'])

    @check_authenticated
    def callback(self):
        if not self.is_callback():
            raise NotFound(self.context, 'callback', self.request)
        # get info from session and request
        token, return_url = self.session.get(self._skey)
        # get auth_token to fetch access_token
        # token should be the request token used to initiate the authorization
        # start an oauth session with all our old tokens from authorize
        oauth = self.oauth_session(token=token)  # should return token
        # now we can update our session with the authorize response
        # TODO: there should be a better way to get the full request url
        authorization_response = self.request.getURL() + '?' + self.request['QUERY_STRING']
        # Parsing the url, updates the state of oauth session as well
        request_token = oauth.parse_authorization_response(authorization_response)
        # TODO: verify request_token somehow?
        # We have got a request token with verifier. (already set in oauth session)
        # Fetch the final access token
        access_token = oauth.fetch_access_token(self.config.access_url)
        # clean up session and store token for user
        if self.session.has_key(self._skey):
            del self.session[self._skey]
        self.setToken(access_token)
        # redirect to last known address?
        self.request.response.redirect(return_url or self.request.getURL())

    @check_authenticated
    def accesstoken(self):
        # FIXME: this is a quick workaround, user parameter should not be here
        # allow for user parameter in case we are admin
        if checkPermission('cmf.ManagePortal', self.context):
            # we are admin ... check if user is set
            username = self.request.form.get('user')
            member = api.user.get(username=username)
            access_token = member.getProperty(self._property, "")
            if access_token:
                access_token = json.loads(access_token)
        else:
            access_token = self.getToken()
        # return full access token for current user
        self.request.response['CONTENT-TYPE'] = 'application/json'
        return json.dumps({
            'oauth_token': access_token['oauth_token'],
            'oauth_token_secret': access_token['oauth_token_secret']
        })

    @check_authenticated
    def clienttoken(self):
        # only admin can fetch client token
        if not checkPermission('cmf.ManagePortal', self.context):
            raise Unauthorized()
        self.request.response['CONTENT-TYPE'] = 'application/json'
        return json.dumps({
            'client_key': self.config.client_key,
            'client_secret': self.config.client_secret,
        })

    # Figshare API
    def validate(self):
        # TODO: OAuth2Session has attribute .authorized ... it only checks for presence of various tokens, but should be a good indicator of successfull authorisation
        token = self.getToken()
        try:
            oauth = self.oauth_session(token=token)

            # params = {
            #     'page': 0,
            #     'status': 'drafts', # private, public
            # }
            params = None

            response = oauth.get('http://api.figshare.com/v1/my_data/articles', params=params)
            #data=json.dumps(body), headers=headers)
            #/articles
            return True
        except Exception as e:
            LOG.info('OAuth validate failed: %s', e)
            return False


# TODO: always the sam e.... IPublishTraverse or ITraverse?
@implementer(IPublishTraverse)
class OAuthTraverser(BrowserView):
    # parse urls like oauth/<serviceid>/<command>

    _serviceid = None
    _view = None

    def publishTraverse(self, context, name):
        # no serviceid yet ? .... name should be it
        if not self._serviceid:
            registry = getUtility(IRegistry)
            coll = registry.collectionOfInterface(IOAuth1Settings)
            for cid, config in coll.items():
                if cid == name:
                    self._serviceid = name
                    self._view = OAuth1View(self.context, self.request, config)
                    return self
            coll = registry.collectionOfInterface(IOAuth2Settings)
            for cid, config in coll.items():
                if cid == name:
                    self._serviceid = name
                    self._view = OAuth2View(self.context, self.request, config)
                    return self
            # raise NotFound
            raise NotFound(self, name, self.request)
        else:
            # we have a serviceid ... name should now be a command
            if name in ('authorize', 'callback', 'accesstoken', 'clienttoken', 'cleartoken'):
                return getattr(self._view, name)
            raise NotFound(self, name, self.request)

    def __call__(self):
        raise BadRequest('Missing parameter')
