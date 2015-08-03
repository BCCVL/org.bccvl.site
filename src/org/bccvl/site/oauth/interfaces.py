from zope.interface import Interface
from zope.schema import ASCIILine, TextLine, URI, Bool


class IOAuth1Settings(Interface):

    id = ASCIILine(
        title=u"ID",
    )

    title = TextLine(
        title=u"Name",
    )

    enabled = Bool(
        title=u"Enabled",
        default=False,
    )

    client_key = TextLine(
        title=u"Client key",
        required=False,
    )
    client_secret = TextLine(
        title=u"Client secret",
        required=False,
    )
    oauth_url = URI(
        title=u"OAuth url",
        required=False,
    )
    authorization_url = URI(
        title=u"Authorization url",
        required=False,
    )
    request_url = URI(
        title=u"Request url",
        required=False,
    )
    access_url = URI(
        title=u"Acces url",
        required=False,
    )

    redirect_url = URI(
        title=u"Redirect url",
        required=False,
    )

    revoke_url = URI(
        title=u"Revoke url",
        required=False,
    )


class IOAuth2Settings(Interface):

    id = ASCIILine(
        title=u"ID",
    )

    title = TextLine(
        title=u"Name",
    )

    enabled = Bool(
        title=u"Enabled",
        default=False,
    )

    client_id = TextLine(
        title=u"Client id",
        required=False,
    )

    client_secret = TextLine(
        title=u"Client secret",
        required=False,
    )

    authorization_url = URI(
        title=u"Authorization url",
        required=False,
    )

    token_url = URI(
        title=u"Token url",
        required=False,
    )
    refresh_url = URI(
        title=u"Refresh url",
        required=False,
    )

    redirect_url = URI(
        title=u"Redirect url",
        required=False,
    )

    revoke_url = URI(
        title=u"Revoke url",
        required=False,
    )
