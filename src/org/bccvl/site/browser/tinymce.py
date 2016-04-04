import json

from Acquisition import aq_inner
from Products.CMFCore.utils import getToolByName
from Products.TinyMCE.browser.browser import TinyMCEBrowserView


class TinyMCECustomBrowserView(TinyMCEBrowserView):

    def jsonConfiguration(self, field):
        """Return the configuration in JSON"""

        utility = getToolByName(aq_inner(self.context), 'portal_tinymce')
        config = utility.getConfiguration(context=self.context,
                                          field=field,
                                          request=self.request)
        config['extended_valid_elements'] = "i*,i[*]"
        config['verify_html'] = False
        return json.dumps(config)
