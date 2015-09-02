from zope.interface import Interface
from zope.schema import ASCIILine, TextLine, URI, Bool


class IOAuth1Settings(Interface):

    id = ASCIILine(
        title=u"ID",
    )

    title = TextLine(
        title=u"Name",
        description=u"Used for display",
    )

    enabled = Bool(
        title=u"Enabled",
        default=False,
    )

    client_key = TextLine(
        title=u"Client key",
        description=u"Key associated with this application",
        required=False,
    )
    client_secret = TextLine(
        title=u"Client secret",
        description=u"Secret associated with this application",
        required=False,
    )

    authorization_url = URI(
        title=u"Authorization url",
        description=u"Url to start user authorization",
        required=False,
    )
    request_url = URI(
        title=u"Request url",
        description=u"Url to request token",
        required=False,
    )
    access_url = URI(
        title=u"Access url",
        description=u"Url to get access token",
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
        required=False,
    )


class IOAuth2Settings(Interface):

    id = ASCIILine(
        title=u"ID",
    )

    title = TextLine(
        title=u"Name",
        description=u"Used for display",
    )

    enabled = Bool(
        title=u"Enabled",
        default=False,
    )

    client_id = TextLine(
        title=u"Client id",
        description=u"ID associated with this application",
        required=False,
    )

    client_secret = TextLine(
        title=u"Client secret",
        description=u"Secret associated with this application",
        required=False,
    )

    authorization_url = URI(
        title=u"Authorization url",
        description=u"Url to start user authorization",
        required=False,
    )

    token_url = URI(
        title=u"Token url",
        description=u"Url to token service",
        required=False,
    )
    refresh_url = URI(
        title=u"Refresh url",
        description=u"Url to token refresh service",
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
        required=False,
    )
