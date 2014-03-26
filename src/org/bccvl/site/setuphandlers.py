from Products.CMFCore.utils import getToolByName
from collective.transmogrifier.transmogrifier import Transmogrifier
from zope.interface import alsoProvides
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
import logging
logger = logging.getLogger(__name__)

AUTH_SCRIPT = """
# check for credentials extracted by extraction script
ipRangeKey = creds.get('ipRangeKey')
if ipRangeKey is None:
    return None
return ('admin', 'admin')
"""

EXTRACT_SCRIPT = """
credentials = {}

# get client IP
clientIP = (request.get('HTTP_X_FORWARDED_FOR') or
            request.get('REMOTE_ADDR', None))
if not clientIP:
    return None

# examine request for IP range
if clientIP.lower() in ('127.0.0.1', 'localhost'):
    credentials['ipRangeKey'] = 'allow'
return credentials
"""


def setupVarious(context):
    logger.info('BCCVL site package setup handler')

    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    # install Products.AutoUserMakerPASPLugin
    qi = getToolByName(portal, 'portal_quickinstaller')
    if 'AutoUserMakerPASPLugin' in (p['id'] for
                                    p in qi.listInstallableProducts()):
        qi.installProduct('AutoUserMakerPASPlugin')

    # install local login pas plugin
    acl = portal.acl_users
    if not 'localscript' in acl:
        factory = acl.manage_addProduct['PluggableAuthService']
        factory.addScriptablePlugin('localscript', 'Local manager access')
    plugin = acl['localscript']
    # add scripts
    factory = plugin.manage_addProduct['PythonScripts']
    if 'extractCredentials' not in plugin:
        factory.manage_addPythonScript('extractCredentials')
        alsoProvides(plugin, IExtractionPlugin)
        script = plugin['extractCredentials']
        script.ZPythonScript_edit('request', EXTRACT_SCRIPT)
    if 'authenticateCredentials' not in plugin:
        factory.manage_addPythonScript('authenticateCredentials')
        script = plugin['authenticateCredentials']
        script.ZPythonScript_edit('creds', AUTH_SCRIPT)
        alsoProvides(plugin, IAuthenticationPlugin)
    if 'localscript' not in acl.plugins.listPluginIds(IExtractionPlugin):
        acl.plugins.activatePlugin(IExtractionPlugin, 'localscript')
    if 'localscript' not in acl.plugins.listPluginIds(IAuthenticationPlugin):
        acl.plugins.activatePlugin(IAuthenticationPlugin, 'localscript')

    # set default front-page
    portal.setDefaultPage('front-page')

    # setup default groups
    groups = [
        {'id': 'Knowledgebase Contributor',
         'title': 'Knowledgebase Contributor',
         #'roles': ['...', '...']
         'description': 'Users in this group can contribute to knowledge base'
         },
        {'id': 'Knowledgebase Editor',
         'title': 'Knowledgebase Editor',
         'description': 'Users in this group can manage knowledgebase content'
         }]
    gtool = getToolByName(portal, 'portal_groups')
    for group in groups:
        if gtool.getGroupById(group['id']):
            gtool.editGroup(**group)
        else:
            gtool.addGroup(**group)

    # setup initial content
    transmogrifier = Transmogrifier(portal)
    transmogrifier(u'org.bccvl.site.dataimport',
                   source={'path': 'org.bccvl.site:initial_content'})
    transmogrifier(u'org.bccvl.site.dataimport',
                   source={'path': 'org.bccvl.compute:content'})
