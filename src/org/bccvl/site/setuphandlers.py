from Products.CMFCore.utils import getToolByName
from collective.transmogrifier.transmogrifier import Transmogrifier

import logging
logger = logging.getLogger(__name__)


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
