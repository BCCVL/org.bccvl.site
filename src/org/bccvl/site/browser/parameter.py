from plone.directives import form
from zope import schema
from z3c.form.browser.radio import RadioFieldWidget
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from zope.schema.fieldproperty import FieldProperty
from decimal import Decimal
from zope.interface import implementer
from z3c.form.object import FactoryAdapter
from persistent import Persistent

from org.bccvl.site import MessageFactory as _

## Base classes for Parameter types


class IParameters(form.Schema):
    pass


class Parameters(Persistent):

    pass


class ParametersFactory(FactoryAdapter):

    factory = Parameters

## BRT

brt_var_monotone_vocab = SimpleVocabulary([
    SimpleTerm(-1, '-1', u'-1'),
    SimpleTerm(1, '+1', u'+1'),
])

brt_family_vocab = SimpleVocabulary.fromItems([
    ('bernoulli (binomial)', 'bernoulli'),
    ('poisson', 'poisson'),
    ('laplace', 'laplace'),
    ('gaussian', 'gaussian'),
])

brt_tolerance_method_vocab = SimpleVocabulary.fromValues([
    'auto',
    'fixed',
])


class IParametersBRT(IParameters):

    tree_complexity = schema.Int(
        title=_(u'tree complexity'),
        default=1,
        description=_(u'The complexity of individual trees between 1 and 50 (inclusive)'),
        min=1,
        max=50,
        required=False,
    )

    learning_rate = schema.Decimal(
        title=_(u'learning rate'),
        description=_(u'The weight applied to individual trees.'),
        default=Decimal('0.01'),
        required=False,
    )

    bag_fraction = schema.Decimal(
        title=_(u'bag fraction'),
        description=_(u'The proportion of observations used in selecting variables.'),
        default=Decimal('0.75'),
        required=False,
    )

    form.widget(var_monotone=RadioFieldWidget)
    var_monotone = schema.Choice(
        title=_(u'var monotone'),
        default=-1,
        vocabulary=brt_var_monotone_vocab,
        required=False,
    )

    n_folds = schema.Int(
        title=_(u'n folds'),
        description=_(u'Number of folds.'),
        default=10,
        required=False,
    )

    prev_stratify = schema.Bool(
        title=_(u'prev stratify'),
        description=_(u'prevalence stratify the folds - only for presence/absence data'),
        default=True,
        required=False,
    )

    family = schema.Choice(
        title=_(u'family'),
        default='bernoulli',
        vocabulary=brt_family_vocab,
        required=False,
    )

    n_trees = schema.Int(
        title=_(u'trees added each cycle'),
        description=_(u'Number of initial trees to fit'),
        default=50,
        required=False,
    )

    max_trees = schema.Int(
        title=_(u'max trees'),
        description=_(u'Max number of trees to fit before stopping'),
        default=1000,
        required=False,
    )

    tolerance_method = schema.Choice(
        title=_(u'tolerance method'),
        description=_(u'Method to use in deciding to stop.'),
        default='auto',
        vocabulary=brt_tolerance_method_vocab,
        required=False,
    )

    tolerance_value = schema.Decimal(
        title=_(u'tolerance value'),
        description=_(u'Tolerance value to use - if method == fixed is absolute, if auto is multiplier * total mean deviance'),
        default=Decimal('0.001'),
        required=False,
    )


@implementer(IParametersBRT)
class ParametersBRT(Parameters):

    tree_complexity = FieldProperty(IParametersBRT['tree_complexity'])
    learning_rate = FieldProperty(IParametersBRT['learning_rate'])
    bag_fraction = FieldProperty(IParametersBRT['bag_fraction'])
    var_monotone = FieldProperty(IParametersBRT['var_monotone'])
    n_folds = FieldProperty(IParametersBRT['n_folds'])
    prev_stratify = FieldProperty(IParametersBRT['prev_stratify'])
    family = FieldProperty(IParametersBRT['family'])
    n_trees = FieldProperty(IParametersBRT['n_trees'])
    max_trees = FieldProperty(IParametersBRT['max_trees'])
    tolerance_method = FieldProperty(IParametersBRT['tolerance_method'])
    tolerance_value = FieldProperty(IParametersBRT['tolerance_value'])


class ParametersBRTFactory(FactoryAdapter):

    factory = ParametersBRT


## BIOCLIM

class IParametersBioclim(IParameters):
    pass


@implementer(IParametersBioclim)
class ParametersBioclim(Parameters):
    pass


class ParametersBioclimFactory(FactoryAdapter):

    factory = ParametersBioclim
