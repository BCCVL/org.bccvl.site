from collective.transmogrifier.transmogrifier import Transmogrifier

import logging
logger = logging.getLogger(__name__)


def setupVarious(context):
    logger.info('BCCVL site package setup handler')

    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    transmogrifier = Transmogrifier(portal)
    transmogrifier(u'org.bccvl.site.dataimport',
                   source={'path': 'org.bccvl.site:initial_content'})
