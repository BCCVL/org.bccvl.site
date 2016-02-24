from zope.annotation.interfaces import IAnnotations
from zope.interface import Interface


class IUserAnnotations(IAnnotations):

    pass


class IUserAnnotationsUtility(Interface):

    def getAnnotations(principal):
        """Return object implementing `IAnnotations` for the given
        `IPrinicipal`.
        If there is no `IAnnotations` it will be created and then returned.
        """

    def getAnnotationsById(principalId):
        """Return object implementing `IAnnotations` for the given
        `prinicipalId`.
        If there is no `IAnnotations` it will be created and then returned.
        """

    def hasAnnotations(principal):
        """Return boolean indicating if given `IPrincipal` has
        `IAnnotations`."""
