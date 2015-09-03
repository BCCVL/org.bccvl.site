from itertools import chain
from z3c.form import button
from z3c.form.form import extends, applyChanges
from z3c.form.interfaces import WidgetActionExecutionError, ActionExecutionError, IErrorViewSnippet, NO_VALUE
from zope.schema.interfaces import RequiredMissing
from org.bccvl.site.interfaces import IJobTracker, IBCCVLMetadata
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.dexterity.browser import add, edit, view
from org.bccvl.site import MessageFactory as _
from zope.interface import Invalid
from plone.z3cform.fieldsets.group import Group
from plone.autoform.base import AutoFields
from plone.autoform.utils import processFields
from plone.supermodel import loadString
from z3c.form.interfaces import DISPLAY_MODE
from z3c.form.error import MultipleErrors
from zope.component import getMultiAdapter
from plone.app.uuid.utils import uuidToCatalogBrain
from decimal import Decimal
from zope.schema.interfaces import IVocabularyFactory
from zope.component import getUtility
import logging

LOG = logging.getLogger(__name__)


# FIXME: probably need an additional widget traverser to inline
#        validate param_groups fields
class ExperimentParamGroup(AutoFields, Group):

    def getContent(self):
        if not hasattr(self.context, 'parameters'):
            return {}
        if not self.toolkit in self.context.parameters:
            return {}
        return self.context.parameters[self.toolkit]

    def update(self):
        # FIXME: stupid autoform thinks if the schema is in schema
        #        attribute and not in additionalSchemata it won't need a
        #        prefix
        # self.updateFieldsFromSchemata()
        #
        # use  processFields instead
        processFields(self, self.schema, prefix=self.toolkit) #, permissionChecks=have_user)

        super(ExperimentParamGroup, self).update()


class ParamGroupMixin(object):
    """
    Mix-in to handle parameter froms
    """

    param_groups = ()

    def addToolkitFields(self):
        groups = []
        # TODO: only sdms have functions at the moment ,... maybe sptraits as well?
        func_vocab = getUtility(IVocabularyFactory, name=self.func_vocab_name)
        functions = getattr(self.context, self.func_select_field, None) or ()
        # TODO: could also use uuidToObject(term.value) instead of relying on BrainsVocabluary terms
        for toolkit in (term.brain.getObject() for term in func_vocab(self.context)):
            if self.mode == DISPLAY_MODE and not self.is_toolkit_selected(toolkit.UID(), functions):
                # filter out unused algorithms in display mode
                continue
            # FIXME: need to cache form schema
            try:
                # FIXME: do some schema caching here
                parameters_model = loadString(toolkit.schema)
            except Exception as e:
                LOG.fatal("couldn't parse schema for %s: %s", toolkit.id, e)
                continue

            parameters_schema = parameters_model.schema

            param_group = ExperimentParamGroup(
                self.context,
                self.request,
                self)
            param_group.__name__ = "parameters_{}".format(toolkit.UID())
            #param_group.prefix = ''+ form.prefix?
            param_group.toolkit = toolkit.UID()
            param_group.schema = parameters_schema
            #param_group.prefix = "{}{}.".format(self.prefix, toolkit.id)
            #param_group.fields = Fields(parameters_schema, prefix=toolkit.id)
            param_group.label = u"configuration for {}".format(toolkit.title)
            if len(parameters_schema.names()) == 0:
                param_group.description = u"No configuration options"
            groups.append(param_group)

        self.param_groups = groups

    def updateFields(self):
        super(ParamGroupMixin, self).updateFields()
        self.addToolkitFields()

    def updateWidgets(self):
        super(ParamGroupMixin, self).updateWidgets()
        # update groups here
        for group in self.param_groups:
            try:
                group.update()
            except Exception as e:
                LOG.info("Group %s failed: %s", group.__name__, e)
        # should group generation happen here in updateFields or in update?

    def extractData(self, setErrors=True):
        data, errors = super(ParamGroupMixin, self).extractData(setErrors)
        for group in self.param_groups:
            groupData, groupErrors = group.extractData(setErrors=setErrors)
            data.update(groupData)
            if groupErrors:
                if errors:
                    errors += groupErrors
                else:
                    errors = groupErrors
        return data, errors

    def applyChanges(self, data):
        changed = super(ParamGroupMixin, self).applyChanges(data)
        # apply algo params:
        new_params = {}
        for group in self.param_groups:
            if self.is_toolkit_selected(group.toolkit, data[self.func_select_field]):
                content = group.getContent()
                param_changed = applyChanges(group, content, data)
                new_params[group.toolkit] = content
        self.context.parameters = new_params

        return changed


# DefaultEditView = layout.wrap_form(DefaultEditForm)
# from plone.z3cform import layout
class View(edit.DefaultEditForm):
    """
    View Experiment
    """

    # id = 'view'
    # enctype = None
    mode = DISPLAY_MODE

    extends(view.DefaultView)

    template = ViewPageTemplateFile("experiment_view.pt")

    label = ''

    def job_state(self):
        return IJobTracker(self.context).state

    # condition=lambda form: form.showApply)
    @button.buttonAndHandler(u'Start Job')
    def handleStartJob(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        msgtype, msg = IJobTracker(self.context).start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)
        self.request.response.redirect(self.context.absolute_url())


class SDMView(ParamGroupMixin, View):
    """
    View SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'functions'

    def is_toolkit_selected(self, tid, data):
        return tid in data


class Edit(edit.DefaultEditForm):
    """
    Edit Experiment
    """

    template = ViewPageTemplateFile("experiment_edit.pt")


class SDMEdit(ParamGroupMixin, Edit):
    """
    Edit SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'functions'

    def is_toolkit_selected(self, tid, data):
        return tid in data


class Add(add.DefaultAddForm):
    """
    Add Experiment
    """

    template = ViewPageTemplateFile("experiment_add.pt")

    extends(view.DefaultView,
            ignoreButtons=True)

    buttons = button.Buttons(add.DefaultAddForm.buttons['cancel'])

    @button.buttonAndHandler(_('Create and start'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        self.validateAction(data)
        if errors:
            self.status = self.formErrorsMessage
            return
        # TODO: this is prob. a bug in base form, because createAndAdd
        #       does not return the wrapped object.
        obj = self.createAndAdd(data)
        if obj is None:
            # TODO: this is probably an error here?
            #       object creation/add failed for some reason
            return
        # get wrapped instance fo new object (see above)
        obj = self.context[obj.id]
        # mark only as finished if we get the new object
        self._finishedAdd = True
        IStatusMessage(self.request).addStatusMessage(_(u"Item created"),
                                                      "info")
        # auto start job here
        jt = IJobTracker(obj)
        msgtype, msg = jt.start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)

    @button.buttonAndHandler(_('Create'), name='create')
    def handleCreate(self, action):
        data, errors = self.extractData()
        self.validateAction(data)
        if errors:
            self.status = self.formErrorsMessage
            return
        # TODO: this is prob. a bug in base form, because createAndAdd
        #       does not return the wrapped object.
        obj = self.createAndAdd(data)
        if obj is None:
            # TODO: this is probably an error here?
            #       object creation/add failed for some reason
            return
        # get wrapped instance fo new object (see above)
        obj = self.context[obj.id]
        # mark only as finished if we get the new object
        self._finishedAdd = True
        IStatusMessage(self.request).addStatusMessage(_(u"Item created"),
                                                      "info")


class SDMAdd(ParamGroupMixin, Add):
    """
    Add SDM Experiment
    """

    portal_type = "org.bccvl.content.sdmexperiment"

    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'functions'

    def is_toolkit_selected(self, tid, data):
        return tid in data

    def create(self, data):
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group data'
        newob = super(SDMAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data on read
        new_params = {}
        for group in self.param_groups:
            if group.toolkit in data['functions']:
                content = group.getContent()
                applyChanges(group, content, data)
                new_params[group.toolkit] = content
        newob.parameters = new_params
        IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def updateWidgets(self):
        super(SDMAdd, self).updateWidgets()
        # TODO: the template checks required to set required class, but
        #       the fields themselves are actually not required (only one or the other)
        self.widgets['species_absence_dataset'].required = True
        self.widgets['species_number_pseudo_absence_points'].required = True

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # data contains already field values
        datasets = data.get('environmental_datasets', {}).keys()
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide error
            raise ActionExecutionError(Invalid('No environmental dataset selected.'))

        # TODO: we should make sure only user picks only one option, otherwise pseudo absence
        #       will be preferred (maybe we can do both?, select absence points, and fill up mith pseudo absences?)
        # we need an absence dataset or a a number of pseudo absence points
        if not data.get('species_pseudo_absence_points'):
            if not data.get('species_absence_dataset'):
                raise ActionExecutionError(RequiredMissing('No absence points selected.'))
        else:
            numabspoints = data.get('species_number_pseudo_absence_points')
            if not numabspoints:
                raise ActionExecutionError(RequiredMissing('No absence points selected'))
            elif numabspoints <= 0:
                raise ActionExecutionError(Invalid('Number of absence points must be greater than 0.'))
        # Determine lowest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        res_vocab = getUtility(IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            idx = res_vocab._terms.index(res_vocab.getTerm(dsbrain.BCCResolution))
            if idx > resolution_idx:
                resolution_idx = idx
        data['resolution'] = res_vocab._terms[resolution_idx].value


class ProjectionAdd(Add):

    portal_type = 'org.bccvl.content.projectionexperiment'

    def create(self, data):
        newob = super(ProjectionAdd, self).create(data)
        # store resolution determined during validateAction
        IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def validateAction(self, data):
        """
        Get resolution from SDM and use it to find future datasets

        TODO: if required layers are not available in future datasets, use current layers from SDM
        """
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific

        # TODO: match result layers with sdm layers and get missing layers from SDM?
        #       -> only environmental? or missing climate layers as well?
        #       do matching here? or in job submit?

        datasets = data.get('future_climate_datasets', [])
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide error
            raise ActionExecutionError(Invalid('No future climate dataset selected.'))
        models = data.get('species_distribution_models', {})
        if not tuple(chain.from_iterable(x for x in models.values())):
            raise ActionExecutionError(Invalid('No source dataset selected.'))

        # Determine lowest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        res_vocab = getUtility(IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            idx = res_vocab._terms.index(res_vocab.getTerm(dsbrain.BCCResolution))
            if idx > resolution_idx:
                resolution_idx = idx
        data['resolution'] = res_vocab._terms[resolution_idx].value


class BiodiverseAdd(Add):

    portal_type = "org.bccvl.content.biodiverseexperiment"

    def validateAction(self, data):
        # TODO: check data ...
        # ...
        datasets = data.get('projection', {})
        if not tuple(chain.from_iterable(x for x in datasets.values())):
            raise ActionExecutionError(Invalid('No projection dataset selected.'))


class EnsembleAdd(Add):

    portal_type = "org.bccvl.content.ensemble"

    def create(self, data):
        newob = super(EnsembleAdd, self).create(data)
        # store resolution determined during validateAction
        IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def validateAction(self, data):
        datasets = list(chain.from_iterable(data.get('datasets', {}).values()))
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide error
            raise ActionExecutionError(Invalid('No dataset selected.'))

        # all selected datasets are combined into one ensemble analysis
        # get resolution for ensembling
        # Determine lowest resolution
        # FIXME: An experiment should store the resolution metadata on the dataset
        #        e.g. an SDM current projection needs to store resolution on tif file
        res_vocab = getUtility(IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            try:
                idx = res_vocab._terms.index(res_vocab.getTerm(dsbrain.BCCResolution))
            except:
                # FIXME: need faster way to order resolutions
                idx = res_vocab._terms.index(res_vocab.getTerm(dsbrain.getObject().__parent__.job_params['resolution']))
            if idx > resolution_idx:
                resolution_idx = idx
        data['resolution'] = res_vocab._terms[resolution_idx].value


class SpeciesTraitsView(ParamGroupMixin, View):
    """
    View SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'traits_functions_source'
    func_select_field = 'algorithm'

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid == data


class SpeciesTraitsEdit(ParamGroupMixin, Edit):
    """
    Edit SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'traits_functions_source'
    func_select_field = 'algorithm'

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid == data


class SpeciesTraitsAdd(ParamGroupMixin, Add):

    portal_type = "org.bccvl.content.speciestraitsexperiment"

    # Parameters for ParamGroupMixin
    func_vocab_name = 'traits_functions_source'
    func_select_field = 'algorithm'

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid == data

    def create(self, data):
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group data'
        newob = super(SpeciesTraitsAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data on read
        new_params = {}
        for group in self.param_groups:
            if group.toolkit == data['algorithm']:
                content = group.getContent()
                applyChanges(group, content, data)
                new_params[group.toolkit] = content
        newob.parameters = new_params
        return newob

    def validateAction(self, data):
        # TODO: check data ...
        pass
