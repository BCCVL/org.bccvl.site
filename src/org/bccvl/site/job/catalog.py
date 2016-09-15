import logging

from AccessControl import ClassSecurityInfo
from BTrees.OOBTree import OOBTree
from Globals import InitializeClass
from AccessControl.Permissions import (
    manage_zcatalog_entries as ManageZCatalogEntries)
from AccessControl.Permissions import search_zcatalog as SearchZCatalog
from Products.CMFPlone.CatalogTool import CatalogTool
from Products.ZCatalog.Catalog import Catalog
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain

from plone import api

from zope.interface import implementer

from org.bccvl.site.job.interfaces import IJobCatalog


LOG = logging.getLogger(__name__)


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


# TODO: maybe use Zope's ZCatalog as base and not Plone's CatalogTool ?
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
    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w'},
    )

    def __init__(self):
        super(JobCatalogTool, self).__init__()
        self._catalog = JobCatalog()
        self.jobs = OOBTree()

    security.declareProtected(SearchZCatalog, 'resolve_path')

    def resolve_path(self, path):
        # Attempt to resolve a job id (path) within this catalog.
        # The path is meant to be  a job id.
        # If no object is found, None is returned.
        # No exceptions are raised.
        try:
            return self.jobs[path]
        except Exception:
            pass

    security.declareProtected(ManageZCatalogEntries, 'clearFindAndRebuild')

    def clearFindAndRebuild(self):
        """
        Empties catalog, then finds all contentish objects (i.e. objects
        with an indexObject method), and reindexes them.
        This may take a long time.
        """
        self.manage_catalogClear()

        for job in self.jobs.values():
            self.reindexObject(job, uid=job.id)

    security.declareProtected(ManageZCatalogEntries, 'reindexIndex')

    def reindexIndex(self, name, REQUEST, pghandler=None):
        if isinstance(name, str):
            name = (name, )

        paths = self._catalog.uids.keys()

        i = 0
        if pghandler:
            pghandler.init('reindexing %s' % name, len(paths))

        for p in paths:
            i += 1
            if pghandler:
                pghandler.report(i)

            obj = self.resolve_path(p)
            if obj is None:
                LOG.error('reindexIndex could not resolve '
                          'an object from the uid %r.' % p)
            else:
                # don't update metadata when only reindexing a single
                # index via the UI
                self.catalog_object(obj, p, idxs=name,
                                    update_metadata=0, pghandler=pghandler)

        if pghandler:
            pghandler.finish()

    # FIXME: either Job objects need to be locatable (SimpleItems)
    #        or we should override a few more methods here (and potentially in Catalog class as well), because currently indexed objects don't have a path or url (they are not Acquisition providers, and are therefore not accessible via traverse?)
    #        - self.catalog_object
    #        - self.resolve_url
    #        - self.resolve_path

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
    addIndex(cat, 'userid', 'FieldIndex')
    addIndex(cat, 'state', 'FieldIndex')
    addIndex(cat, 'content', 'FieldIndex')
    addIndex(cat, 'created', 'DateIndex')
    addIndex(cat, 'lsid', 'FieldIndex')
    addIndex(cat, 'type', 'FieldIndex')
    addIndex(cat, 'function', 'FieldIndex')

    # cat.addColumn('name')
    addColumn(cat, 'id')
    addColumn(cat, 'state')
    addColumn(cat, 'content')
