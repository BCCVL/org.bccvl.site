from decimal import Decimal
from itertools import chain
import csv
import json
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.publisher.browser import TestRequest as TestRequestBase
from plone.app.z3cform.interfaces import IPloneFormLayer
import os.path
from urlparse import urlparse
from org.bccvl.site import defaults
from org.bccvl.site.content.interfaces import ISDMExperiment
from org.bccvl.tasks.datamover import DataMover


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
            'form.widgets.species_occurrence_dataset': [unicode(self.occur.UID())],  # ABT
            'form.widgets.species_absence_dataset': [unicode(self.absen.UID())],
            'form.widgets.species_pseudo_absence_points': [],
            'form.widgets.resolution': ('Resolution2_5m', ),
            # FIXME: shouldn't be necessary to use unicode here,... widget converter should take care of it
            'form.widgets.environmental_datasets.item.0': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.item.0.item': [u'B01'],
            'form.widgets.environmental_datasets.item.1': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.item.1.item': [u'B02'],
            'form.widgets.environmental_datasets.count': '2',
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
            'form.widgets.projection.dataset.0.0.threshold': u'0.5',
            'form.widgets.cluster_size': '5000',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newBiodiverse")
        return form


class EnsembleExperimentHelper(object):
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
                               name="newEnsemble")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My EN Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.experiment_type': ISDMExperiment.__identifier__,
            'form.widgets.datasets.count': '1',
            'form.widgets.datasets.experiment.0': unicode(self.sdmexp.UID()),
            'form.widgets.datasets.dataset.0': [unicode(self.sdmproj.UID())],
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newEnsemble")
        return form


class SpeciesTraitsExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal):
        # configure local variables on instance
        self.portal = portal
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.algorithm = self.portal[defaults.TOOLKITS_FOLDER_ID]['lm']
        # get some dataset shortcuts
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.traitsds = self.datasets['traits.csv']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesTraits")
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
            'form.widgets.IDublinCore.title': u"My ST Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.algorithm': [self.algorithm.UID()],
            'form.widgets.formula': u'Z ~ X + Y',
            'form.widgets.data_table': [unicode(self.traitsds.UID())]
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesTraits")
        return form


class MockDataMover(DataMover):

    targetpath = None
    ala_dataset = None
    ala_metadata = None
    ala_occurrence = None

    def move(self, move_args):
        params = move_args[0]
        self.targetpath = urlparse(params[1]).path
        # generate fake data
        self.ala_dataset = {
            'files': [
                { 'url': os.path.join(self.targetpath, 'ala_occurrence.csv'),
                  'dataset_type': 'occurrences',
                  'size': 0
                },
                { 'url': os.path.join(self.targetpath, 'ala_metadata.json'),
                  'dataset_type': 'attribution',
                  'size': 0
                }
            ],
            'provenance': {
                'url': 'source_url',
                'source': 'ALA',
                'source_data': '01/01/2001'
            },
            'num_occurrences': 5,
            'description': 'Observed occurrences for Black Banded Winged Pearl Shell (Pteria penguin), imported from ALA on 04/08/2015',
            'title': 'Black Banded Winged Pearl Shell (Pteria penguin) occurrences'
        }
        self.ala_metadata = {
            'taxonConcept': {
                'nameString': 'Pteria penguin',
                'guid': 'urn:lsid:biodiversity.org.au:afd.taxon:dadb5555-d286-4862-b1dd-ea549b1c05a5',
            },
            'classification': {
                'guid': 'urn:lsid:biodiversity.org.au:afd.taxon:dadb5555-d286-4862-b1dd-ea549b1c05a5',
                'scientificName': 'Pteria penguin',
                'rank': 'species',
                'rankId': '7000',
                'kingdom': 'ANIMALIA',
                'kingdomGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:4647863b-760d-4b59-aaa1-502c8cdf8d3c',
                'phylum': 'MOLLUSCA',
                'phylumGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:4fb59020-e4a8-4973-adca-a4f662c4645c',
                'clazz': 'BIVALVIA',
                'clazzGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:0c18b965-d1e9-4518-8c21-72045a340a4b',
                'order': 'PTERIOIDA',
                'orderGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:f4d97823-14fb-4eb2-a980-9a62d5ee8f08',
                'family': 'PTERIIDAE',
                'familyGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:d6300a23-1386-4620-9cb8-0ce481ab4988',
                'genus': 'Pteria',
                'genusGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:3a97cb93-351e-443f-addd-624eb5b2278c',
                'species': 'Pteria penguin',
                'speciesGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:dadb5555-d286-4862-b1dd-ea549b1c05a5',
            },
            'commonNames': [
                {'nameString': 'Black Banded Winged Pearl Shell'},
            ]
        }
        self.ala_occurrence = [
            ['species', 'lon', 'lat'],
            ['Pteria penguin', '145.453448', '-14.645126'],
            ['Pteria penguin', '145.850', '-5.166'],
            ['Pteria penguin', '167.68167', '-28.911835'],
            ['Pteria penguin', '114.166', '-21.783'],
            ['Pteria penguin', '147.283', '-18.633'],
        ]
        # return fake state
        return [{'status': 'PONDING', 'id': 1}]

    def wait(self, states, sleep=10):
        # write fake data to files
        with open(os.path.join(self.targetpath, 'ala_dataset.json'), 'w') as fp:
            json.dump(self.ala_dataset, fp, indent=2)
        with open(os.path.join(self.targetpath, 'ala_metadata.json'), 'w') as fp:
            json.dump(self.ala_metadata, fp, indent=2)
        with open(os.path.join(self.targetpath, 'ala_occurrence.csv'), 'wb') as fp:
            csvwriter = csv.writer(fp)
            for data in self.ala_occurrence:
                csvwriter.writerow(data)
        # return fake status
        return [{'status': 'COMPLETED', 'id': 1}]
