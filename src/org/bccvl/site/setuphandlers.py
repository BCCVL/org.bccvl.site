from org.bccvl.site import defaults
from plone.app.dexterity.behaviors import constrains
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes

import logging
logger = logging.getLogger(__name__)


def setupVarious(context):
    logger.info('BCCVL site package setup handler')
    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return

    portal = context.getSite()
    createDatasetsFolder(portal)
    createFunctionsFolder(portal)
    createKnowledgeBaseFolder(portal)

    createExperimentsFolder(portal)


def _createFolder(context, folder_id, folder_title, workflow_state='publish', log_msg=None):
    # helper function for adding structural locations
    if not folder_id in context:
        if log_msg is None:
            log_msg = 'Creating container in %s for %s (%s)' % (context.title, folder_title,folder_id)
        logger.info(log_msg)
        folder_id = context.invokeFactory('Folder', folder_id, title=folder_title)
        context.portal_workflow.doActionFor(context[folder_id], workflow_state)
    return context[folder_id]


def createDatasetsFolder(site):
    # Add a root level container to hold dataset objects
    _createFolder(site,
        folder_id = defaults.DATASETS_FOLDER_ID,
        folder_title = 'Reference Data Sets',
    )
    # Add sub-folders for various set types
    datasets = site[defaults.DATASETS_FOLDER_ID]
    _createFolder(datasets,
        folder_id = defaults.DATASETS_SPECIES_FOLDER_ID,
        folder_title = 'Biological Data',
    )
    _createFolder(datasets,
        folder_id = defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID,
        folder_title = 'Environmental Data',
    )
    _createFolder(datasets,
        folder_id = defaults.DATASETS_CLIMATE_FOLDER_ID,
        folder_title = 'Climate Data'
    )


def createFunctionsFolder(site):
    # Add a root level container to hold functions
    folder = _createFolder(site,
        folder_id = defaults.FUNCTIONS_FOLDER_ID,
        folder_title = 'Functions',
    )
    constr = ISelectableConstrainTypes(folder)
    constr.setConstrainTypesMode(constrains.ENABLED)
    constr.setLocallyAllowedTypes(['Document', 'org.bccvl.content.function'])
    # set these as well otherwise plone.app.contentmenu chokes on None list
    # plone.app.contentmenu-2.0.8-py2.7.egg/plone/app/contentmenu/menu.py(558)getMenuItems()
    constr.setImmediatelyAddableTypes(['Document', 'org.bccvl.content.function'])


def createKnowledgeBaseFolder(site):
    # Add a root level container to hold knowledge base articles
    _createFolder(site,
        folder_id = defaults.KNOWLEDGEBASE_FOLDER_ID,
        folder_title = 'Knowledge Base',
    )


def createExperimentsFolder(site):
    # TODO: make this per-user rather than global
    _createFolder(site,
        folder_id = defaults.EXPERIMENTS_FOLDER_ID,
        folder_title = 'Experiments',
    )
    # TODO: DEFINITELY do NOT use this in production!!
    site.experiments.manage_permission('Add portal content', ('Authenticated',), acquire=False)
    site.experiments.manage_permission('Modify portal content', ('Authenticated',), acquire=False)
