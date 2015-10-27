import unittest
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from Products.CMFPlone.interfaces.constrains import ISelectableConstrainTypes
from Products.CMFCore.utils import getToolByName
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID


def selectedRoles(obj, permission):
    for role in obj.rolesOfPermission(permission):
        if role['selected'] == 'SELECTED':
            yield role['name']


def selectedPermissions(obj, role):
    for perm in obj.permissionsOfRole(role):
        if perm['selected'] == 'SELECTED':
            yield perm['name']


class SiteSetupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def test_site_structure(self):
        portal = self.layer['portal']

        self.assertTrue(defaults.DATASETS_FOLDER_ID in portal)
        dsf = portal[defaults.DATASETS_FOLDER_ID]
        self.assertTrue(defaults.DATASETS_SPECIES_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_CLIMATE_FOLDER_ID in dsf)

        self.assertTrue(defaults.TOOLKITS_FOLDER_ID in portal)
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
        setRoles(portal, TEST_USER_ID, [])

    def test_permissions_for_roles(self):
        portal = self.layer['portal']
        roles = {'Manager': ['org.bccvl: Add Experiment',
                             'org.bccvl: Add Function',
                             'org.bccvl: Add Dataset']}
        for role, perms in roles.items():
            permissions = tuple(selectedPermissions(portal, role))
            for perm in perms:
                self.assertIn(perm, permissions,
                              "check {} has permission '{}'".format(role, perm))

    def test_not_permissions_for_roles(self):
        portal = self.layer['portal']
        roles = {'Member': ['org.bccvl: Add Experiment',
                            'org.bccvl: Add Function',
                            'org.bccvl: Add Dataset']}
        for role, perms in roles.items():
            permissions = tuple(selectedPermissions(portal, role))
            for perm in perms:
                self.assertNotIn(perm, permissions,
                                 "check {} has not permission '{}'".format(role, perm))

    def test_groups_local_roles(self):
        portal = self.layer['portal']
        kb = portal[defaults.KNOWLEDGEBASE_FOLDER_ID]
        roles = kb.get_local_roles()
        kb_roles = {'Knowledgebase Contributor': ['Knowledgebase Contributor'],
                    'Knowledgebase Editor': ['Knowledgebase Editor']}
        for group, roles in kb_roles.items():
            self.assertIn(group, roles)
            self.assertEqual(kb_roles[group], roles)

    def test_groups(self):
        portal = self.layer['portal']
        gt = getToolByName(portal, 'portal_groups')
        # groups get Authenticated role per default
        groups = {'Knowledgebase Contributor': {'roles': ['Authenticated']},
                  'Knowledgebase Editor': {'roles': ['Authenticated']}}
        for group, values in groups.items():
            pg = gt.getGroupById(group)
            self.assertIsNotNone(pg)
            self.assertEqual(pg.getRoles(), values['roles'])
            # gt.getGroupMembes(group_id)
            # gt.getGroupsForPrincipal(principal)
            # gt.getGroupInfo(gruop_id)
            # gt.getGroupsByUserId(user_id)
            # gt.setGroupOwnership(group,object)

    def test_initial_content_published(self):
        # make sure fronte-page and knowledgebase are published
        portal = self.layer['portal']
        for id, wf_name, state in (
                (defaults.KNOWLEDGEBASE_FOLDER_ID, 'intranet_workflow', 'external'),
                (defaults.DATASETS_FOLDER_ID, 'intranet_workflow', 'internally_published'),
                (defaults.EXPERIMENTS_FOLDER_ID, 'intranet_workflow', 'internally_published'),
                ('/'.join((defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_CLIMATE_FOLDER_ID)), 'intranet_workflow', 'internally_published'),
                ('/'.join((defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_SPECIES_FOLDER_ID)), 'intranet_workflow', 'internally_published'),
                ('/'.join((defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID)), 'intranet_workflow', 'internally_published'),
                ('front-page', 'simple_publication_workflow', 'published')):
            content = portal.restrictedTraverse(id)
            wf_tool = getToolByName(portal, 'portal_workflow')
            chain = wf_tool.getChainFor(content)
            # only one workflow chain
            self.assertEqual(len(chain), 1)
            # our custom simple pub workflow
            self.assertEqual(chain[0], wf_name)
            # is the state published?
            wf_state = wf_tool.getStatusOf(chain[0], content)
            self.assertEqual(wf_state['review_state'], state)

    def test_add_experiment_permission(self):
        portal = self.layer['portal']
        pt = portal['portal_types']
        fti = pt['org.bccvl.content.sdmexperiment']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddExperiment')
        fti = pt['org.bccvl.content.projectionexperiment']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddExperiment')

    def test_add_function_permission(self):
        portal = self.layer['portal']
        pt = portal['portal_types']
        fti = pt['org.bccvl.content.function']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddFunction')

    def test_add_dataset_permission(self):
        portal = self.layer['portal']
        pt = portal['portal_types']
        fti = pt['org.bccvl.content.dataset']
        self.assertEqual(fti.add_permission, 'org.bccvl.AddDataset')

    def test_permission_mapping(self):
        # FIXME: this tests our easy testing permissions and should
        #        change to harden the system
        portal = self.layer['portal']
        experiments = portal[defaults.EXPERIMENTS_FOLDER_ID]
        # FIXME: Allow ever Member to add anything within expermiments
        result = experiments.permission_settings(permission='Add portal content')[0]
        self.assertEqual(result['acquire'], 'CHECKED')
        roles = sorted(selectedRoles(experiments, 'Add portal content'))
        self.assertEqual(roles, ['Manager', 'Member'])
