from zope.component import queryMultiAdapter
from z3c.form.field import Fields
from z3c.form.form import DisplayForm
from plone.app.dexterity.behaviors.metadata import IDublinCore
#from plone.dexterity.browser.view import DefaultView
from org.bccvl.site.content.dataset_base import DatasetFieldMixin


#class DatasetDisplayView(DatasetFieldMixin, DefaultView):
class DatasetDisplayView(DatasetFieldMixin, DisplayForm):

    # TODO: could use @additionalSchemata again now that rightsstatement is custom field

    @property
    def fields(self):
        genreschemata = self.getGenreSchemata()
        fields = Fields(IDublinCore).select('title', 'description')
        if genreschemata:
            fields += Fields(*genreschemata)
        return fields

    def __call__(self):
        # FIXME: need a way to display file as is and to display normal content view
        #        e.g. register another view? ... make display-file the default and
        #        view the metadata view? (will need to supply /view everywhere?)
        # FIXME: maybe rework? default is download/display for all datasets, or append/view to see landing page?
        # FIXME: what about remote datasets? need to redirect
        if ((getattr(self.context, 'file', None) is not None and
             self.context.format in ('image/png', 'text/html'))):
            view = queryMultiAdapter((self.context, self.request),
                                     name='display-file')
            if view is not None:
                return view()
        # support subclassed forms which do not call update on their superclass
        self.update()
        return self.index()
        #return super(DatasetDisplayView, self).__call__()
