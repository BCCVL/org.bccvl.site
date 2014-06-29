from plone.dexterity.content import Container
from zope.interface import implementer
from org.bccvl.site.api import dataset

# BBB: backwards compatible import
from .interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IEnsembleExperiment, ISpeciesTraitsExperiment)


@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    # TODO: remove this method, it's global API
    def future_climate_datasets(self):
        return dataset.find_projections(self, self.emission_scenarios,
                                        self.climate_models, self.years)


@implementer(IBiodiverseExperiment)
class BiodiverseExperiment(Container):

    pass


@implementer(IEnsembleExperiment)
class EnsembleExperiment(Container):

    pass


@implementer(ISpeciesTraitsExperiment)
class SpeciesTraitsExperiment(Container):

    pass
