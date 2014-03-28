from plone.dexterity.content import Container
from zope.interface import implementer
from Products.CMFCore.utils import getToolByName
from gu.z3cform.rdf.interfaces import IGraph
from ordf.namespace import DC as DCTERMS


# BBB: backwards compatible import
from .interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment)


@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    functions = ('org.bccvl.compute.predict.execute', )

    def future_climate_datasets(self):
        # TODO: use QueryApi?
        return find_projections(self, self.emission_scenarios,
                                self.climate_models, self.years)


# TODO: turn this into some adapter lookup component-> maybe use
# z3c.form validation adapter lookup?
def find_projections(ctx, emission_scenarios, climate_models, years):
        """compile points into list of datasets"""
        pc = getToolByName(ctx, 'portal_catalog')
        result = []
        brains = pc.searchResults(BCCEmissionScenario=emission_scenarios,
                                  BCCGlobalClimateModel=climate_models)
        for brain in brains:
            graph = IGraph(brain.getObject())
            # TODO: do better date matching
            year = graph.value(graph.identifier, DCTERMS['temporal'])
            if year in years:
                # TODO: yield?
                result.append(brain)
        return result


@implementer(IBiodiverseExperiment)
class BiodiverseExperiment(Container):

    pass
