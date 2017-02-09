from plone.dexterity.content import Container
from zope.interface import implementer
# BBB: backwards compatible import
from .interfaces import (
    ISDMExperiment, IMSDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IEnsembleExperiment, ISpeciesTraitsExperiment, IMigratoryExperiment)


@implementer(ISDMExperiment)
class SDMExperiment(Container):

    pass


@implementer(IMSDMExperiment)
class MSDMExperiment(Container):

    pass


@implementer(IMigratoryExperiment)
class MigratoryExperiment(Container):

    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    pass


@implementer(IBiodiverseExperiment)
class BiodiverseExperiment(Container):

    pass


@implementer(IEnsembleExperiment)
class EnsembleExperiment(Container):

    pass


@implementer(ISpeciesTraitsExperiment)
class SpeciesTraitsExperiment(Container):

    pass
