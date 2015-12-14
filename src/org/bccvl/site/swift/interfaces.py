from zope.interface import Interface
from plone.supermodel import model
from zope import schema


class ISwiftUtility(Interface):

    def generate_temp_url(path, duration=300, method='GET'):
        """Generate temp url which is valid for duration seconds

        path ... full path to object including version and account
        """

# Temp_url:
#    ... need temp_url_key and storage_url set up
# Swift results:
#    ... need result_container (has default) and storage_url set up
# All need CORS header setup on containers for visualiser
# TODO: should have extra flag to decide whether to store in swift or locally.... to ensure temp_urls work but results don't go into swift (low priority)
class ISwiftSettings(model.Schema):

    auth_url = schema.URI(
        title=u"Auth URL",
        description=u"Usually something like http://keystone.example.com/v2",
        required=False
    )

    auth_version = schema.TextLine(
        title=u"Auth version",
        description=u"Usually something like '1' or '2'",
        required=False
    )

    storage_url = schema.URI(
        title=u"Swift storage URL",
        description=u"The storage url including version and account",
        required=False
    )

    temp_url_key = schema.TextLine(
        title=u"Swift temp URL key",
        description=u"Key used to generate swift temp URLs",
        required=False
    )

    result_container = schema.TextLine(
        title=u"Result container",
        description=u"Container to store results in",
        default=u"results",
        required=False,
    )
