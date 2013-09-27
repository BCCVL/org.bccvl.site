from org.bccvl.site import defaults
from plone.app.dexterity.behaviors import constrains
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from collective.setuphelpers.structure import setupStructure
from collective.setuphelpers import setupNavigation
from plone.dexterity.utils import createContent
from plone.app.contenttypes.setuphandlers import  addContentToContainer
from Products.CMFCore.utils import getToolByName

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
    createFrontPage(portal)

# TODO: fix up collective.setuphelpers
#    setupStructure(portal, SITE_STRUCTURE)
#    setupStructure(portal, DATASETS_STRUCTURE)

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
        folder_id = defaults.TOOLKITS_FOLDER_ID,
        folder_title = defaults.TOOLKITS_FOLDER_TITLE,
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


def createFrontPage(site):
    if 'front-page' not in site.keys():
        page = createContent('Document', id='front-page',
                             title=u'Welcome to BCCVL',
                             description=u'Congratulations! You have successfully installed BCCVL')
        page = addContentToContainer(site, page)
        site.setDefaultPage('front-page')
        wftool = getToolByName(site, "portal_workflow")
        wftool.doActionFor(page, 'publish')



#def _folder(title, id):
#    return dict(
#        title = title,
#        id = id,
#        type = 'Folder'
#    )
#
#SITE_STRUCTURE = [
#    _folder(defaults.DATASETS_FOLDER_TITLE, defaults.DATASETS_FOLDER_ID),
#    _folder(defaults.TOOLKITS_FOLDER_TITLE, defaults.TOOLKITS_FOLDER_ID),
#    _folder(defaults.KNOWLEDGEBASE_FOLDER_TITLE, defaults.KNOWLEDGEBASE_FOLDER_ID),
#    _folder(defaults.EXPERIMENTS_FOLDER_TITLE, defaults.EXPERIMENTS_FOLDER_ID),
#]
#
#DATASETS_STRUCTURE = [
#    _folder(defaults.DATASETS_SPECIES_FOLDER_TITLE, defaults.DATASETS_SPECIES_FOLDER_ID),
#    _folder(defaults.DATASETS_ENVIRONMENTAL_FOLDER_TITLE, defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID),
#    _folder(defaults.DATASETS_CLIMATE_FOLDER_ID, defaults.DATASETS_CLIMATE_FOLDER_ID),
#]
