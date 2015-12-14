from plone.app.contentlisting import catalog
from plone.app.contenttypes.interfaces import IFile


class ContentListingObject(catalog.CatalogContentListingObject):

    def Format(self):
        ob = self.getObject()
        # TODO: protect adainst acquisition here?
        if IFile.providedBy(ob):
            mime = ob.file.contentType
        else:
            mime = getattr(ob, 'format', 'application/octet-stream')
        return mime
