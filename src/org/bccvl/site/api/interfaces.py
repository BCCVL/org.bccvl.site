from zope.publisher.interfaces.browser import IBrowserPublisher
from zope.interface import Interface

class IAPIPublisher(Interface):
    """
    Wraps APIs and makes them accessible as
    xmlrpc, json(-ld), endpoints.
    """
    pass
