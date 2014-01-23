from plone.app.contentlisting import catalog
from plone.app.contenttypes.interfaces import IFile


class ContentListingObject(catalog.CatalogContentListingObject):

    def Format(self):
        ob = self.getObject()
        mime = 'application/octet-stream'
        if IFile.providedBy(ob):
            mime = ob.file.contentType
        return mime
