import unittest2 as unittest
import doctest
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING
from org.bccvl.site.interfaces import IBCCVLMetadata
from plone.testing import layered
from plone.namedfile import NamedFile
from plone.uuid.interfaces import IUUID
import transaction

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
    result = sdm.invokeFactory('Folder',
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
    md = IBCCVLMetadata(sdmds)
    md.update({
        'genre': 'DataGenreCP',
        'species': {
            'scientificName': u'Result species',
        }
    })
    sdmds.reindexObject()

    # create a fake projection experiment
    proj = portal.experiments.invokeFactory('org.bccvl.content.projectionexperiment',
                                            id='proj',
                                            title=u'Test Projection')
    proj = portal.experiments[proj]
    # create a result folder
    result = proj.invokeFactory('Folder',
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
    md = IBCCVLMetadata(rds)
    md.update({
        'genre': 'DataGenreFP',
        'year': 2014,
        'gcm': 'cccma-cgcm31',
        'emsc': 'RCP3PD',
        'species': {
            'scientificName': u'Result species',
        }
    })
    # update index with data from graph
    rds.reindexObject()

    # we have to commit here because doctests run in a different
    # thread because they connect via test-broswer.
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
