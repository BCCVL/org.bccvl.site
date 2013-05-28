from plone.directives import form
from zope import schema
from plone.namedfile import field


class IBCCVLGroup(form.Schema):

    title = schema.TextLine(
        title=u"Name",
        required=True,
        description=u"Group name",
        )

    logo = field.NamedBlobImage(
        title=u"Group Logo",
        required=False,
        )

    homepage = schema.TextLine(
        # url format
        #title=_(u"External Homepage"),
        title=u"External Homepage",
        required=False,
    #constraint=is_url,
        )

    form.widget(bio="plone.app.z3cform.wysiwyg.WysiwygFieldWidget")
    bio = schema.Text(
    #title=_(u"Biography"),
    title=u"Biography",
        required=False,
        )
