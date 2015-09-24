from .interfaces import IOAuth2Settings
from zope.schema import URI


class IDropbox(IOAuth2Settings):

    authorization_url = URI(
        title=u"Authorization url",
        description=u"Url to start user authorization",
        default="https://www.dropbox.com/1/oauth2/authorize",
        required=False,
    )

    token_url = URI(
        title=u"Token url",
        description=u"Url to token service",
        default="https://api.dropbox.com/1/oauth2/token",
        required=False,
    )

    refresh_url = URI(
        title=u"Refresh url",
        description=u"Url to token refresh service",
        default="https://api.dropbox.com/1/oauth2/token",
        required=False,
    )

    redirect_url = URI(
        title=u"Redirect url",
        description=u"Url to redirect to after successful authorization",
        required=False,
    )

    revoke_url = URI(
        title=u"Revoke url",
        description=u"Url to revoke authorization",
        # Google OAuth2 would also have programmatic web endpoint to revoke access
        default="https://api.dropboxapi.com/1/disable_access_token",
        required=False,
    )


# TODO: registration should be done via zcml?
from .vocabulary import oauth_providers

oauth_providers.add_provider(IDropbox, u'Dropbox')
