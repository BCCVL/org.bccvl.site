import unittest2 as unittest
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID


def selectedRoles(obj, permission):
    for role in obj.rolesOfPermission(permission):
        if role['selected'] == 'SELECTED':
            yield role['name']


class SiteSetupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def test_site_structure(self):
        portal = self.layer['portal']

        self.assertTrue(defaults.DATASETS_FOLDER_ID in portal)
        dsf = portal[defaults.DATASETS_FOLDER_ID]
        self.assertTrue(defaults.DATASETS_SPECIES_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_CLIMATE_FOLDER_ID in dsf)

        self.assertTrue(defaults.FUNCTIONS_FOLDER_ID in portal)
        self.assertTrue(defaults.KNOWLEDGEBASE_FOLDER_ID in portal)

    def test_allowed_contenttypes(self):
        portal = self.layer['portal']
        ff = ISelectableConstrainTypes(portal[defaults.FUNCTIONS_FOLDER_ID])
        # not possible as test user
        self.assertEqual(len(ff.allowedContentTypes()), 0)
        # but if we become Manager
        setRoles(portal, TEST_USER_ID, ['Manager'])
        self.assertEqual(['Document', 'org.bccvl.content.function'],
                         [fti.id for fti in ff.allowedContentTypes()])
        # let's be Member again
        setRoles(portal, TEST_USER_ID, ['Member'])

    def test_add_experiment_permission(self):
        portal = self.layer['portal']
        pt = portal['portal_types']
        fti = pt['org.bccvl.content.experiment']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddExperiment')

    def test_add_function_permission(self):
        portal = self.layer['portal']
        pt = portal['portal_types']
        fti = pt['org.bccvl.content.function']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddFunction')

    def test_roles(self):
        portal = self.layer['portal']
        roles = tuple(selectedRoles(portal, "org.bccvl: Add Experiment"))
        self.assertEqual(roles,
                         ('Manager', ))
        roles = tuple(selectedRoles(portal, "org.bccvl: Add Function"))
        self.assertEqual(roles,
                         ('Manager', ))
