from zope.interface import implementer
from zope.component import adapter
from zope.annotation import IAnnotations, IAttributeAnnotatable
from persistent.dict import PersistentDict
from org.bccvl.site.interfaces import IBCCVLMetadata

# TODO: this will become future work to enhance performance by
# reducing the amonut of queries we have to do against the triple
# store (no more direkt data fetching from triple store, as we don't
# utilise the full power anyway)
# TODO: will this adapter do a write on read? (should be avoided)


KEY = 'org.bccvl.site.content.metadata'


@implementer(IBCCVLMetadata)
@adapter(IAttributeAnnotatable)
class BCCVLMetadata(object):
    '''
    Adapter to manage additional metadata for BCCVL Datasets.
    '''

    __marker = object()

    def __init__(self, context):
        self.context = context
        annotations = IAnnotations(context)
        self._md = annotations.setdefault(KEY, PersistentDict())

    def __getitem__(self, key):
        return self._md.__getitem__(key)

    def __setitem__(self, key, value):
        return self._md.__setitem__(key, value)

    def __delitem__(self, key):
        return self._md.__delitem__(key)

    def update(self, *args, **kw):
        return self._md.update(*args, **kw)

    def get(self, k, default=None):
        return self._md.get(k, default)

    def keys(self):
        return self._md.keys()

    def __iter__(self):
        return self._md.__iter__()

    def setdefault(self, key, default):
        return self._md.setdefault(key, default)

    def pop(self, key, default=__marker):
        if default is self.__marker:
            return self._md.pop(key)
        return self._md.pop(key, default)
