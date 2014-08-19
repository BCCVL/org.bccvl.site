import unittest2 as unittest
import doctest
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING
from plone.testing import layered
from gu.z3cform.rdf.interfaces import IGraph
from org.bccvl.site.namespace import BCCVOCAB, BCCPROP, BCCEMSC, BCCGCM, DWC
from ordf.namespace import DC
from rdflib import Literal
from gu.z3cform.rdf.interfaces import IORDF
from zope.component import getUtility
from plone.namedfile import NamedFile
from plone.uuid.interfaces import IUUID

# setup site with content
# run doctest in xmlrpc package (rename to api or move to sep. package someday)


def setUpApiTests(doctest):
    """
    set up some test data for api doctests as test user
    """
    layer = doctest.globs['layer']
    # layer: app, portal, request,
    #        configurationContext, host, port, zodbDB
    portal = layer['portal']
    # create a fake sdm experiment
    sdm = portal.experiments.invokeFactory('org.bccvl.content.sdmexperiment',
                                           id='sdm',
                                           title=u'Test SDM')
    sdm = portal.experiments[sdm]
    result = sdm.invokeFactory('gu.repository.content.RepositoryItem',
                               id='sdmresult')
    result = sdm[result]
    result.job_params = {
        'function': 'bioclim',
    }
    sdmds = result.invokeFactory('org.bccvl.content.dataset',
                                 id='sdmrds',
                                 title=u'Result Test SDM RData',
                                 file=NamedFile(filename=u'Result_file.Rdata'))
    sdmds = result[sdmds]

    # create a fake projection experiment
    proj = portal.experiments.invokeFactory('org.bccvl.content.projectionexperiment',
                                            id='proj',
                                            title=u'Test Projection')
    proj = portal.experiments[proj]
    # create a result folder
    result = proj.invokeFactory('gu.repository.content.RepositoryItem',
                                id='projresult')
    result = proj[result]
    result.job_params = {
        'species_distribution_models': [IUUID(sdmds)],
    }
    # create a result dataset
    rds = result.invokeFactory('org.bccvl.content.dataset',
                               id='rds',
                               title=u'Result Test',
                               file=NamedFile(filename=u'Result_file.tiff'))
    rds = result[rds]
    # set metadata on rds
    rdsgraph = IGraph(rds)
    rdsgraph.add((rdsgraph.identifier, BCCPROP['datagenre'], BCCVOCAB['DataGenreFP']))
    rdsgraph.add((rdsgraph.identifier, DC['temporal'], Literal(u"start=2014;")))
    rdsgraph.add((rdsgraph.identifier, BCCPROP['gcm'], BCCGCM['cccma-cgcm31']))
    rdsgraph.add((rdsgraph.identifier, BCCPROP['emissionscenario'], BCCEMSC['RCP3PD']))
    rdsgraph.add((rdsgraph.identifier, DWC['scientificName'], Literal(u"Result species")))
    handler = getUtility(IORDF).getHandler()
    handler.put(rdsgraph)
    # update index with data from graph
    # TODO: do I need to put stuff for reindexing as well?
    rds.reindexObject()
    # TODO: do I have to commit? (put is necessary for commit)
    import transaction
    transaction.commit()


def tearDownApiTests(doctest):

    pass


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        layered(doctest.DocFileSuite('api.txt',
                                     package='org.bccvl.site.browser',
                                     setUp=setUpApiTests,
                                     tearDown=tearDownApiTests,
                                     optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE),
                layer=BCCVL_FUNCTIONAL_TESTING),
        layered(doctest.DocFileSuite('dataset.txt',
                                     package='org.bccvl.site.api',
                                     setUp=setUpApiTests,
                                     tearDown=tearDownApiTests,
                                     optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE),
                layer=BCCVL_FUNCTIONAL_TESTING),
    ])
    return suite
