from Products.Five.browser import BrowserView

from zope.component import getUtility
from plone.registry.interfaces import IRegistry

from org.bccvl.site.browser.interfaces import IRavenConfig


TEMPLATE = u"""
        (function() {{
        //define(['raven'], function(Raven) {{
            Raven.config('{public_dsn}', {{
                whitelistUrls: [ /.*\.bccvl\.org\.au/ ]
            }}).install()

            // could also get logged in user details from server if available
            var username = $('#user-menu .bccvl-username').text()
            if (username) {{
                Raven.setUserContext({{
                    name: username
                }})
            }}

            $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {{
                Raven.captureException(new Error(thrownError || jqXHR.statusText), {{
                    extra: {{
                        type: ajaxSettings.type,
                        url: ajaxSettings.url,
                        data: ajaxSettings.data,
                        status: jqXHR.status,
                        error: thrownError || jqXHR.statusText,
                        response: jqXHR.responseText.substring(0, 100)
                    }}
                }});
            }});
        }})();
"""


class Raven(BrowserView):

    def __call__(self):
        response = self.request.response
        response.setHeader('content-type', 'text/javascript;;charset=utf-8')

        registry = getUtility(IRegistry)
        dsn = registry.forInterface(IRavenConfig).public_dsn
        if dsn:
            return TEMPLATE.format(
                public_dsn=dsn
            )

        return u""
