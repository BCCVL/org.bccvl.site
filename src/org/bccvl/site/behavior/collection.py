"""Behavior to store additional collection level metadata.


"""

from plone.app.textfield import RichText as RichTextField
from plone.autoform.interfaces import IFormFieldProvider
from plone.supermodel import model
from zope.interface import provider
from zope.schema import List


@provider(IFormFieldProvider)
class ICollection(model.Schema):

    model.fieldset(
        'ownership',
        label='Ownership',
        fields=('attribution', 'external_description')
    )

    attribution = List(
        title=u'Citation and Attribution',
        description=u'',
        required=False,
        value_type=RichTextField(),
    )

    external_description = RichTextField(
        title=u'Full description:',
        description=u'Text describing access to the external landing page',
        required=False,
    )
