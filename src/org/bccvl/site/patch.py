
# this should be sent upstream to z3c.form.converter:
#   in case the siglecheckbox-empty-marker is not present in the request,
#   the widget extracts NO_VALUE and passes this on to this converter.toFieldValue
#   which expects the value to be a list.
#   other option would be to make NO_VALUE evaluate to False. bool(NO_VALUE)
#-> possibly related to custom singlechockboxwidget in plone.z3cform? (which renders a radio as workaround?)
#-> empt-marker no longer needed on checkbox

from plone.app.dexterity.behaviors.exclfromnav import IExcludeFromNavigation

IExcludeFromNavigation['exclude_from_nav'].required = False


# plone.namedfile uses blob.consumeFile when loading data from a file
# object/descriptor consumeFile tries to be efficient and moves the
# file instead of copying it. This may have unwanted side effects,
# like on a transaction abort it won't restore the original file. (bad
# for conflicterror retries)
from zope.interface import implements
from plone.namedfile.interfaces import IStorage
from plone.namedfile.interfaces import NotStorable
import shutil


class FileDescriptorStorable(object):
    implements(IStorage)

    def store(self, data, blob):
        if not isinstance(data, file):
            raise NotStorable("Could not store data (not of 'file').")

        # The original used consumeFile which tries to move a file if possible
        # filename = getattr(data, "name", None)
        # if filename is not None:
        #     blob.consumeFile(filename)
        #     return
        # Let us use any file object and just copy it
        import logging
        logging.getLogger("BLOB PATCH").info("USE MY BLOB STORAGE ADAPTER")
        dest = blob.open('w')
        # TODO: should we seek to 0?
        shutil.copyfileobj(data, dest)


# updated boolean html attributes to cover html 5 attributes
BOOLEAN_HTML_ATTRS = frozenset([
    # List of Boolean attributes in HTML that should be rendered in
    # minimized form (e.g. <img ismap> rather than <img ismap="">)
    # From http://www.w3.org/TR/xhtml1/#guidelines (C.10)
    # TODO: The problem with this is that this is not valid XML and
    # can't be parsed back!
    "compact", "nowrap", "ismap", "declare", "noshade", "checked",
    "disabled", "readonly", "multiple", "selected", "noresize",
    "defer", "required"
])


boolean_html_attrs = lambda: BOOLEAN_HTML_ATTRS  # Now we have a callable method!


def apply_patched_const(scope, original, replacement):
    """
    Helper method for collective.monkeypatcher to replace
    module level constants.
    """
    setattr(scope, original, replacement())
    return
