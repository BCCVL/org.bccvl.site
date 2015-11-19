import logging
import requests
import transaction
from transaction.interfaces import IDataManager
from zope.component import getUtility
from zope.interface import implementer
from org.bccvl.site.swift.interfaces import ISwiftUtility


LOG = logging.getLogger(__name__)

# TODO: This could be generic if we pass a callback instead of dataset
#       into the data manager.
#       This way this datamanger would act  like a
#       post commit hook but would also be called / removed on
#       savepoint commit / rollback
@implementer(IDataManager)
class SwiftDataManager(object):

    def __init__(self, dataset):

        self.dataset = dataset
        self.transaction_manager = transaction.manager

    def sortKey(self):
        return 'swift' + str(id(self))

    def _do_nothing(self, transaction):
        pass
    abort = commit = tpc_begin = tpc_vote = tpc_abort = _do_nothing

    def tpc_finish(self, tx):

        # transaction.interfaces implies that exceptions are
        # a bad thing.  assuming non-dire repercussions, and that
        # we're not dealing with remote (non-zodb) objects,
        # swallow exceptions.
        try:
            tool = getUtility(ISwiftUtility)
            temp_url = tool.generate_temp_url(url=self.dataset.remoteUrl,
                                              method='DELETE')
            import ipdb; ipdb.set_trace()
            r = requests.delete(temp_url)
            # Make sure we raise an exception in case of an error
            r.raise_for_status()
            # TODO: should we be worried if there is a redirect?
        except Exception, e:
            # TODO: maybe use tx.log instance? (has transaction name assigned)
            LOG.exception('Some error happened while removing SWIFT object %s: %s',
                          self.dataset.remoteUrl, e)
            # TODO: due to a bug? in smift, if we get a 404 the erquest was probably successful anyway

def dataset_removed(obj, event):
    # We'll do the delet in swift with a datamaneger
    # to make sure the object still exists in case the transaction
    # get's rolled back
    transaction.get().join(SwiftDataManager(obj))
