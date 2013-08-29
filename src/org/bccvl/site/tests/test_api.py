import unittest2 as unittest
import doctest
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING


# setup site with content
# run doctest in xmlrpc package (rename to api or move to sep. package someday)

from plone.testing import layered
def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        layered(doctest.DocFileSuite('api.txt', package='org.bccvl.site.browser',
                                     optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE),
                layer=BCCVL_FUNCTIONAL_TESTING),
    ])
    return suite
