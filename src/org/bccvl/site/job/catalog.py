from AccessControl import ClassSecurityInfo
from BTrees.OOBTree import OOBTree
from Globals import InitializeClass
from Products.CMFCore.permissions import ManagePortal
from Products.CMFPlone.CatalogTool import CatalogTool
from Products.ZCatalog.Catalog import Catalog
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain

from plone import api

from zope.interface import implementer

from org.bccvl.site.job.interfaces import IJobCatalog


class JobCatalog(Catalog):
    """
    Custom inner Catalog, which implements a different class for brains
    """

    def useBrains(self, brains):
        """ Customise the brains we use, because our indexed objects are not
        locatable via path.
        """

        class mybrains(AbstractCatalogBrain, brains):

            def getURL(self, relative=0):
                return None

            def _unrestrictedGetObject(self):
                """Return the object for this record
                Same as getObject, but does not do security checks.
                """
                return self.__parent__.jobs[self.getPath()]

            def getObject(self, REQUEST=None):
                """Return the object for this record
                Will return None if the object cannot be found via its cataloged path
                (i.e., it was deleted or moved without recataloging), or if the user is
                not authorized to access the object.
                This method mimicks a subset of what publisher's traversal does,
                so it allows access if the final object can be accessed even
                if intermediate objects cannot.
                """
                # FIXME: do security check here
                return self.__parent__.jobs[self.getPath()]

        scopy = self.schema.copy()

        schema_len = len(self.schema.keys())
        scopy['data_record_id_'] = schema_len
        scopy['data_record_score_'] = schema_len + 1
        scopy['data_record_normalized_score_'] = schema_len + 2

        mybrains.__record_schema__ = scopy

        self._v_brains = brains
        self._v_result_class = mybrains


@implementer(IJobCatalog)
class JobCatalogTool(CatalogTool):
    """
    A specific catalog for indexing Jobs.
    """

    title = 'Job Catalog'
    id = 'job_catalog'
    portal_type = meta_type = 'JobCatalog'
    plone_tool = 1

    security = ClassSecurityInfo()
    _properties=(
        {'id':'title', 'type': 'string', 'mode':'w'},
    )

    jobs = OOBTree()

    def __init__(self):
        super(JobCatalogTool, self).__init__()
        self._catalog = JobCatalog()

    security.declareProtected(ManagePortal, 'clearFindAndRebuild')
    def clearFindAndRebuild(self):
        """
        Empties catalog, then finds all contentish objects (i.e. objects
        with an indexObject method), and reindexes them.
        This may take a long time.
        """

        def indexObject(obj, path):
            self.reindexObject(obj)

        self.manage_catalogClear()

        portal = api.portal.get()
        import ipdb; ipdb.set_trace()
        # FIXME: change root to traverse from, ... make sure that our simple objects are found
        portal.ZopeFindAndApply(portal,
                                #""" put your meta_type here """,
                                obj_metatypes=(),
                                search_sub=True, apply_func=indexObject)


InitializeClass(JobCatalogTool)


def setup_job_catalog(portal):
    if 'job_catalog' not in portal:
        pass

    def addIndex(cat, id, *args):
        if id not in cat.indexes():
            cat.addIndex(id, *args)

    def addColumn(cat, id, *args):
        if id not in cat.schema():
            cat.addColumn(id, *args)

    cat = api.portal.get_tool('job_catalog')  # do interface lookup?
    #cat.addIndex('name', 'type', 'attribute/method')
    addIndex(cat, 'id', 'FieldIndex')
    addIndex(cat, 'user', 'FieldIndex')
    addIndex(cat, 'state', 'FieldIndex')
    addIndex(cat, 'content', 'FieldIndex')


    #cat.addColumn('name')
    addColumn(cat, 'id')
    addColumn(cat, 'state')
    addColumn(cat, 'content')
