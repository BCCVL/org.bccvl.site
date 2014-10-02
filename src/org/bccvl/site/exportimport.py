import logging
import xml.etree.ElementTree as ET
from collective.transmogrifier.transmogrifier import Transmogrifier


LOG = logging.getLogger(__name__)


def dataimport(context, logger=None):
    """Import step that looks for bccvl_dataimport.xml and uses
    org.bccvl.site.dataimport transmogrifier pipeline to import
    content.
    """
    if logger is None:
        logger = LOG

    xml = context.readDataFile('bccvl_dataimport.xml')
    if xml is None:
        LOG.debug('Nothing to import.')
        return

    LOG.info('Importing BCCVL content.')
    root = ET.fromstring(xml)

    portal = context.getSite()
    transmogrifier = Transmogrifier(portal)

    for node in root:
        if node.tag not in ('import', ):
            raise ValueError('Unknown node: {0}'.format(node.tag))
        pipeline = node.get('pipeline', u'org.bccvl.site.dataimport')

        # extract pipeline parameters
        # TODO: at the moment params can only be applied to a
        #       transmogrifier section named 'source'
        params = {}
        for pnode in node:
            if pnode.tag not in ('param', ):
                raise ValueError('Unknown node: {0}'.format(pnode.tag))
            name = pnode.get('name')
            if name is None:
                raise ValueError('Missing attribute name on param tag')
            value = pnode.get('value')
            if value is None:
                raise ValueError('Missing attribute value on param tag')
            # TODO: support parameter typing and more complex parameters?
            params[name] = value

        # TODO: current  dataimport pipeline requires path parameter for source
        #       do I need to resolve path somehow?
        transmogrifier(pipeline, source=params)
