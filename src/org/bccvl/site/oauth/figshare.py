from .interfaces import IOAuth1Settings
from zope.schema import URI


class IFigshare(IOAuth1Settings):

    authorization_url = URI(
        title=u"Authorization url",
        description=u"Url to start user authorization",
        default="http://api.figshare.com/v1/pbl/oauth/authorize",
        required=False,
    )
    request_url = URI(
        title=u"Request url",
        description=u"Url to request token",
        default="http://api.figshare.com/v1/pbl/oauth/request_token",
        required=False,
    )
    access_url = URI(
        title=u"Access url",
        description=u"Url to get access token",
        default="http://api.figshare.com/v1/pbl/oauth/access_token",
        required=False,
    )

    revoke_url = URI(
        title=u"Revoke url",
        description=u"Url to revoke authorization",
        default="http://figshare.com/account/applications",
        required=False,
    )


# TODO: registration should be done via zcml?
from .vocabulary import oauth_providers

oauth_providers.add_provider(IFigshare, u'Figshare')
