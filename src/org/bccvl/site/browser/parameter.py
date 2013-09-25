from plone.directives import form
from zope import schema
from z3c.form.browser.radio import RadioFieldWidget
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from decimal import Decimal
from zope.interface import implementer
from zope.interface import Interface
from zope.component import adapts
from z3c.form.interfaces import IObjectFactory
from persistent.dict import PersistentDict

from org.bccvl.site import MessageFactory as _

## Base classes for Parameter types

class IParameters(form.Schema):
    pass

class Parameters(PersistentDict):
    def __init__(self, value=None):
        super(Parameters, self).__init__()
        if value is not None:
            self.update(value)

@implementer(IObjectFactory)
class ParametersFactory(object):
    adapts(Interface, Interface, Interface, Interface)

    def __init__(self, context, request, form, widget):
        self.context = context
        self.request = request
        self.form = form
        self.widget = widget

## BRT

brt_var_monotone_vocab = SimpleVocabulary([
    SimpleTerm(-1, '-1', u'-1'),
    SimpleTerm( 1, '+1', u'+1'),
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
        title = _(u'tree complexity'),
        default = 1,
        description = _(u'between 1 and 50 (inclusive)'),
        min = 1, max = 50,
        required = False,
    )

    learning_rate = schema.Decimal(
        title = _(u'learning rate'),
        default = Decimal('0.01'),
        required = False,
    )
    
    bag_fraction = schema.Decimal(
        title = _(u'bag fraction'),
        default = Decimal('0.75'),
        required = False,
    )

    form.widget(var_monotone=RadioFieldWidget)
    var_monotone = schema.Choice(
        title = _(u'var monotone'),
        default = -1,
        vocabulary = brt_var_monotone_vocab,
        required = False,
    )
    
    n_folds = schema.Int(
        title = _(u'n folds'),
        default = 10,
        required = False,
    )
    
    prev_stratify = schema.Bool(
        title = _(u'prev stratify'),
        description = _(u'stratify the folds?'),
        default = True,
        required = False,
    )
    
    family = schema.Choice(
        title = _(u'family'),
        default = 'bernoulli',
        vocabulary = brt_family_vocab,
        required = False,
    )

    n_trees = schema.Int(
        title = _(u'trees added each cycle'),
        default = 50,
        required = False,
    )
    
    max_trees = schema.Int(
        title = _(u'max trees'),
        default = 1000,
        required = False,
    )
    
    tolerance_method = schema.Choice(
        title = _(u'tolerance method'),
        default = 'auto',
        vocabulary = brt_tolerance_method_vocab,
        required = False,
    ) 
    
    tolerance_value = schema.Decimal(
        title = _(u'tolerance value'),
        default = Decimal('0.001'),
        required = False,
    )

@implementer(IParametersBRT)
class ParametersBRT(Parameters):
    pass

class ParametersBRTFactory(ParametersFactory):
    def __call__(self, value):
        return ParametersBRT(value)


## BIOCLIM

class IParametersBioclim(IParameters):
    pass

@implementer(IParametersBioclim)
class ParametersBioclim(Parameters):
    pass

class ParametersBioclimFactory(ParametersFactory):
    def __call__(self, value):
        return ParametersBioclim(value)
    
