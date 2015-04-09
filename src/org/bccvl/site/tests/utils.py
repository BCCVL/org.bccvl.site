from itertools import chain
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.component import getMultiAdapter
from zope.interface import alsoProvides, implementer
from zope.publisher.browser import TestRequest as TestRequestBase
from plone.app.z3cform.interfaces import IPloneFormLayer

from org.bccvl.site import defaults


@implementer(IPloneFormLayer, IAttributeAnnotatable)
class TestRequest(TestRequestBase):
    """Zope 3's TestRequest doesn't support item assignment, but Zope 2's
    request does.
    """
    def __setitem__(self, key, value):
        pass



class SDMExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal):
        # configure local variables on instance
        self.portal = portal
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # get some dataset shortcuts
        self.algorithm = self.portal[defaults.TOOLKITS_FOLDER_ID]['bioclim']
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        abt = self.datasets[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']
        self.occur = abt['occurrence.csv']
        self.absen = abt['absence.csv']
        self.current = self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesDistribution")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with default values
        data = {}
        for widget in chain(
                form.widgets.values(),
                # skip standard plone groups
                #chain.from_iterable(g.widgets.values() for g in form.groups),
                chain.from_iterable(g.widgets.values() for g in form.param_groups)):
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.functions': [self.algorithm.UID()],  # BIOCLIM
            'form.widgets.species_occurrence_dataset': unicode(self.occur.UID()),  # ABT
            'form.widgets.species_absence_dataset': unicode(self.absen.UID()),
            'form.widgets.species_absence_points': [],
            'form.widgets.resolution': ('Resolution2_5m', ),
            # FIXME: shouldn't be necessary to use unicode here,... widget converter should take care of it
            'form.widgets.environmental_datasets.dataset.0': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.layer.0': u'B01',
            'form.widgets.environmental_datasets.dataset.1': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.layer.1': u'B02',
            'form.widgets.environmental_datasets.count': '3',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesDistribution")
        return form
        

class ProjectionExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal, sdmexp):
        # configure local variables on instance
        self.portal = portal
        self.sdmexp = sdmexp
        self.sdmmodel = sdmexp.values()[0]['model.RData']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # get some dataset shortcuts
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.future = self.datasets[defaults.DATASETS_CLIMATE_FOLDER_ID]['future']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newProjection")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My CC Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.species_distribution_models': unicode(self.sdmexp.UID()),
            'form.widgets.species_distribution_models.model': [unicode(self.sdmmodel.UID())],
            'form.widgets.future_climate_datasets': [unicode(self.future.UID())]
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newProjection")
        return form
        

class BiodiverseExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal, sdmexp):
        # configure local variables on instance
        self.portal = portal
        self.sdmexp = sdmexp
        self.sdmproj = sdmexp.values()[0]['proj_test.tif']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]


    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newBiodiverse")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My BD Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.projection.count': '1',
            'form.widgets.projection.experiment.0': unicode(self.sdmexp.UID()),
            'form.widgets.projection.dataset.0.count': 1,
            'form.widgets.projection.dataset.0.0.uuid': unicode(self.sdmproj.UID()),
            'form.widgets.projection.dataset.0.0.threshold': '0.0',
            'form.widgets.cluster_size': '5000',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newBiodiverse")
        return form
    
