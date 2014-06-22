from plone.dexterity.content import Container
from zope.interface import implementer
from org.bccvl.site.api import dataset

# BBB: backwards compatible import
from .interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IFunctionalResponseExperiment,  IEnsembleExperiment,
    ISpeciesTraitsExperiment)


@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    # TODO: get rid of these functions tuples
    functions = ('org.bccvl.compute.predict.execute', )

    # TODO: remove this method, it's global API
    def future_climate_datasets(self):
        return dataset.find_projections(self, self.emission_scenarios,
                                        self.climate_models, self.years)


@implementer(IBiodiverseExperiment)
class BiodiverseExperiment(Container):

    functions = ('org.bccvl.compute.biodiverse.execute', )


@implementer(IFunctionalResponseExperiment)
class FunctionalResponseExperiment(Container):

    functions = ('org.bccvl.compute.functresp.execute', )


@implementer(IEnsembleExperiment)
class EnsembleExperiment(Container):

    functions = ('org.bccvl.compute.ensemble.execute', )


@implementer(ISpeciesTraitsExperiment)
class SpeciesTraitsExperiment(Container):

    functions = ('org.bccvl.compute.speciestraits.execute', )
