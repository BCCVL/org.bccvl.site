from Products.Five import BrowserView


# FIXME: this view needs to exist for default browser layer as well
#        otherwise diazo.off won't find the page if set up.
#        -> how would unthemed markup look like?
#        -> theme would only have updated template.
class DatasetsUploadView(BrowserView):
    """
    upload datasets view
    """
