from BTrees.OOBTree import OOBTree
from persistent.dict import PersistentDict
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer

from org.bccvl.site.userannotation.interfaces import IUserAnnotationsUtility, IUserAnnotations

# CONTINUE:
#   .. add setup code for annotation storage to setup handlers? (and migration step)
#   .. register global utility
#   .. implement and register user adapter? (which interface User, Member?, also IUserAnnotations or IAnnotations?)
#   .. migrate oauth.py to use this tool


def init_user_annotation():
    portal = api.portal.get()
    annotations = IAnnotations(portal)
    if 'org.bccvl.site.userannotation' not in annotations:
        annotations['org.bccvl.site.userannotation'] = OOBTree()

# TODO: add cleanup helper?
# TODO: add migration from properties
#       -> also clean up propertysheet afterwards
# TODO: add event when user get's deleted, delete annotations as well?


@implementer(IUserAnnotationsUtility)
class PrincipalAnnotationUtility(object):
    """Stores `IAnnotations` for `IPrinicipals`.
    The utility ID is 'PrincipalAnnotation'.
    """

    _annotations = None

    @property
    def annotations(self):
        if self._annotations is None:
            portal = api.portal.get()
            self._annotations = IAnnotations(portal)['org.bccvl.site.userannotation']
        return self._annotations

    def getAnnotations(self, principal):
        """Return object implementing IAnnotations for the given principal.
        If there is no `IAnnotations` it will be created and then returned.
        """
        return self.getAnnotationsById(principal.id)

    def getAnnotationsById(self, principalId):
        """Return object implementing `IAnnotations` for the given principal.
        If there is no `IAnnotations` it will be created and then returned.
        """
        return UserAnnotation(principalId, self.annotations)

    def hasAnnotations(self, principal):
        """Return boolean indicating if given principal has `IAnnotations`."""
        return principal.id in self.annotations


@implementer(IUserAnnotations)
class UserAnnotation(object):
    """Stores annotations."""

    def __init__(self, principalId, store=None):
        self.principalId = principalId
        # _v_store is used to remember a mapping object that we should
        # be saved in if we ever change
        self._v_store = store
        self._data = PersistentDict() if store is None else store.get(principalId, PersistentDict())

    def __bool__(self):
        return bool(self._data)

    __nonzero__ = __bool__

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __setitem__(self, key, value):
        if self._v_store is not None:
            # _v_store is used to remember a mapping object that we should
            # be saved in if we ever change
            self._v_store[self.principalId] = self._data
            del self._v_store

        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __contains__(self, key):
        return key in self._data

    def items(self):
        return self._data.items()


# TODO: adapter for IPropertiedUser? (or any super interface? or IMember?)
# @component.adapter(IPrincipal)
# @interface.implementer(IAnnotations)
# def annotations(principal, context=None):
#     utility = component.getUtility(IPrincipalAnnotationUtility, context=context)
#     return utility.getAnnotations(principal)
