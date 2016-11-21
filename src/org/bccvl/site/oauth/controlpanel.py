#
import uuid

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
from zope.schema.interfaces import IVocabularyFactory

from org.bccvl.site.oauth.interfaces import IOAuth2Client


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
        prefix = str(self.context.id)
        fields = field.Fields(self.schema, prefix=prefix)
        # TODO: Do we need to have id visible?
        #       id may be used to associate user id's with oauth credentials
        self.fields = fields.omit('id', prefix=prefix)
        # Need a button profix to separate our own action
        self.buttons.prefix = prefix
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


class CreateNewForm(form.AddForm):
    # A subform used to add new OAuth provider configurations
    # It is a basic AddForm that ignores the context

    fields = field.Fields(
        Choice(
            __name__='provider',
            title=u'Provider',
            vocabulary='org.bccvl.site.oauth.providers'),
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
        collif = data.get('provider')  # the value here is already the vocab value (not the token)
        coll = registry.collectionOfInterface(collif)
        if coll is not None:
            normalizer = getUtility(IIDNormalizer)
            # is new id an str object or unicode?
            newid = normalizer.normalize(data.get('name'))
            # FIXME: check if id already exists
            rec = coll.add(newid)
            rec.id = newid  # used as form prefix in edit subforms
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
        vocab = getUtility(IVocabularyFactory, 'org.bccvl.site.oauth.providers')(self.context)
        groups = []
        for term in vocab:
            coll = registry.collectionOfInterface(term.value, check=False)
            # how to check if coll is empty? -> if yes skip
            for rid, record in coll.items():
                subform = OAuthBaseGroup(record, self.request, self)
                subform.schema = term.value
                subform.label = record.title or term.title or record.id or rid
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


class OAuthClientControlPanelForm(RegistryEditForm):

    form.extends(RegistryEditForm)

    template = ViewPageTemplateFile('clientcontrolpanel.pt')

    # no schema needed to drive this form
    schema = IOAuth2Client
    schema_prefix = None

    # form states ....
    #   listing: show list of existing clients, and allow crud operations
    #   edit:    show single client by id and allow editing
    #   view:    show settings for single client (easy copy/paste of settings?)
    state = 'listing'

    def __init__(self, context, request):
        super(OAuthClientControlPanelForm, self).__init__(context, request)

    def getContent(self):
        return getUtility(IRegistry).forInterface(
            self.schema,
            check=False,
            prefix=self.schema_prefix)

    def clients(self):
        coll = getUtility(IRegistry).collectionOfInterface(IOAuth2Client)
        # TODO: sort by id or key (coll is a dictionary)?
        for key, value in coll.items():
            yield {
                'id': key,
                'client': value
            }

    def _create_new_id(self):
        new_id = unicode(uuid.uuid4())
        if not new_id[0].isalpha():
            new_id = u'{}{}'.format(
                chr(ord('a') + int(new_id[0])),
                new_id[1:]
            )
        return new_id

    def create_new_item(self):
        coll = getUtility(IRegistry).collectionOfInterface(IOAuth2Client)
        new_id = self._create_new_id()

        while new_id in coll:
            new_id = self._create_new_id()

        new_rec = coll.add(new_id)
        new_rec.client_id = new_id
        new_rec.title = u'New Client'
        return new_id

    def update(self):
        self.item_action = self.request.get('item_action')
        if self.item_action not in ('Add', 'Edit', 'Delete'):
            return
        if self.item_action == 'Add':
            self.item_id = self.create_new_item()
            self.item_action = 'Edit'
        else:
            self.item_id = self.request.get('item_id')
        if not self.item_id:
            return
        if self.item_action == 'Delete':
            coll = getUtility(IRegistry).collectionOfInterface(self.schema)
            del coll[self.item_id]
            return
        self.state = 'item'
        self.schema_prefix = '{}/{}.'.format(self.schema.__identifier__, self.item_id)
        super(OAuthClientControlPanelForm, self).update()

    def updateFields(self):
        super(OAuthClientControlPanelForm, self).updateFields()


# Wrap form into a view class
OAuthClientControlPanelView = layout.wrap_form(OAuthClientControlPanelForm,
                                               ControlPanelFormWrapper)
OAuthClientControlPanelView.label = u"OAuth Clients"
