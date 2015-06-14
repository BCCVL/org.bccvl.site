#
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.registry.interfaces import IRegistry
from plone.z3cform import layout
from z3c.form import form, field, button
from z3c.form.interfaces import IWidgets, IGroup
from zope.component import getUtility, getMultiAdapter
from zope.interface import implementer
from zope.location import locate
from zope.schema import Choice, TextLine

from .interfaces import IOAuth1Settings, IOAuth2Settings


@implementer(IGroup)
class OAuthBaseGroup(form.EditForm):
    # Sub / group form

    label = u"OAuth configuration"

    schema = None

    def __init__(self, context, request, parentForm):
        super(OAuthBaseGroup, self).__init__(context, request)
        self.parentForm = parentForm

    def update(self):
        # This form can be multiple times on the page,
        # so we have to make sure that the fields get
        # a unique prefix
        self.fields = field.Fields(self.schema,
                                   prefix=str(self.context.id))
        # Need a button profix to separate our own action
        self.buttons.prefix = str(self.context.id)
        super(OAuthBaseGroup, self).update()

    def updateWidgets(self, prefix=None):
        '''See interfaces.IForm'''
        # We have our own idea whether we want to ignoreContext within this
        # group or not (z3c default is to use same setting as in parentForm)
        self.widgets = getMultiAdapter(
            (self, self.request, self.getContent()), IWidgets)
        for attrName in ('mode', 'ignoreRequest',
                         'ignoreReadonly'):
            value = getattr(self.parentForm.widgets, attrName)
            setattr(self.widgets, attrName, value)
        if prefix is not None:
            self.widgets.prefix = prefix
        self.widgets.update()
        self.updateActions()

    @button.buttonAndHandler(u'Remove configuration')
    def delRecord(self, action):
        data, errors = self.extractData()
        # TODO: check errors
        registry = getUtility(IRegistry)
        # delete record and do same redirect as in add (as 303)
        coll = registry.collectionOfInterface(self.schema)
        del coll[self.context.id]
        self.request.response.redirect(self.request.getURL(), 303)


class OAuth1EditForm(OAuthBaseGroup):
    # a gorup form to handle OAuth1 configurations

    # id, label, __name__, description
    label = u"OAuth 1 - Figshare"

    schema = IOAuth1Settings


class OAuth2EditForm(OAuthBaseGroup):
    # a group form to handle OAuth1 configurations

    # id, label, __name__, description
    label = u"OAuth 2 - Google"

    schema = IOAuth2Settings


class CreateNewForm(form.AddForm):
    # A subform used to add new OAuth provider configurations
    # It is a basic AddForm that ignores the context

    fields = field.Fields(
        Choice(
            __name__='provider',
            title=u'Provider',
            values=('OAuth 2', 'OAuth 1')),
        TextLine(
            __name__='name',
            required=False,
            title=u'Name'),
    )

    def create(self, data):
        # TODO: check errors
        registry = getUtility(IRegistry)
        coll = None
        rec = None
        if data.get('provider') == 'OAuth 1':
            coll = registry.collectionOfInterface(IOAuth1Settings)
        elif data.get('provider') == 'OAuth 2':
            coll = registry.collectionOfInterface(IOAuth2Settings)
        if coll is not None:
            normalizer = getUtility(IIDNormalizer)
            # is new id an str object or unicode?
            newid = normalizer.normalize(data.get('name'))
            rec = coll.add(newid)
            rec.id = newid
            rec.title = data.get('name')
        return rec

    def add(self, obj):
        # create already did the add
        # TODO: if obj is None we probably have a problem somewhere
        self._finishedAdd = True

    def render(self):
        # Override render so that we can set our own http status in case
        # of redirect
        # TODO: add some confirmation message somehow?
        #       IStatusMessage for succes
        #       and maybe self.errorMessage as error?
        # can't use 201 as browsers won't do the redirect on a 2xx code
        # 302 / 307 (307 is more specific) might do as  well
        if self._finishedAdd:
            self.request.response.redirect(self.nextURL(), 303)
            # shortcut content ceration
            return ""
        return super(CreateNewForm, self).render()


class OAuthControlPanelForm(RegistryEditForm):
    # A form with two subforms
    # 1. a small form to add new configurations
    #    - handle create
    # 2. a form with one group form for each existing configuration
    #    - handle edit and delete

    form.extends(RegistryEditForm)

    template = ViewPageTemplateFile('controlpanel.pt')

    # no schema needed to drive this form
    schema = None

    # part 1 of the form (part 2 is this form itself)
    addform = None

    def __init__(self, context, request):
        super(OAuthControlPanelForm, self).__init__(context, request)
        self.addform = CreateNewForm(context, request)

    def getContent(self):
        # TODO: there is something borked with setting ignoreContext
        #       when I hit save it tries to persist the fields in this form
        #       to whatever is returned here (None causes troubles which
        #       should be fine for a from with ignoreContext=True)
        return {}

    def updateFields(self):
        super(OAuthControlPanelForm, self).updateFields()
        # This is the place to add groups.
        #    superclass groups have been created now,
        #    and it won't mess with ours.
        #    we can also add GroupFactory here, because update
        #    will take care of it
        registry = getUtility(IRegistry)
        coll = registry.collectionOfInterface(IOAuth1Settings, check=False)
        groups = []
        for rid, record in coll.items():
            # TODO: prefix of record id?
            subform = OAuth1EditForm(record, self.request, self)
            subform.label = record.title or record.id or rid
            locate(subform, self, record.id or rid)
            groups.append(subform)
        coll = registry.collectionOfInterface(IOAuth2Settings, check=False)
        for rid, record in coll.items():
            # TODO: prefix of record id?
            subform = OAuth2EditForm(record, self.request, self)
            subform.label = record.title or record.id or rid
            locate(subform, self, record.id or rid)
            groups.append(subform)
        self.groups += tuple(groups)

    def update(self):
        self.addform.update()
        # TODO check response for shortcut (if addform.update
        #      executed it's action the response is probably
        #      already set to redirect?)
        super(OAuthControlPanelForm, self).update()


# Wrap form into a view class
OAuthControlPanelView = layout.wrap_form(OAuthControlPanelForm,
                                         ControlPanelFormWrapper)
OAuthControlPanelView.label = u"OAuth settings"
