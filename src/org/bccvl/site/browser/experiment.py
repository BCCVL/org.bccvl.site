from collections import OrderedDict
from itertools import chain
from z3c.form import button
from z3c.form.form import extends
from z3c.form.interfaces import WidgetActionExecutionError, ActionExecutionError, IErrorViewSnippet, NO_VALUE
from zope.schema.interfaces import RequiredMissing
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.interfaces import IExperimentJobTracker
#from org.bccvl.site.stats.interfaces import IStatsUtility
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.dexterity.browser import add, edit, view
from org.bccvl.site import MessageFactory as _
from zope.interface import Invalid
from plone import api
from plone.z3cform.fieldsets.group import Group
from plone.autoform.base import AutoFields
from plone.autoform.utils import processFields
from plone.supermodel import loadString
from z3c.form.interfaces import DISPLAY_MODE
from z3c.form.error import MultipleErrors
from zope.component import getMultiAdapter
from plone.app.uuid.utils import uuidToCatalogBrain, uuidToObject
from decimal import Decimal
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.component import getUtility
from z3c.form.interfaces import IDataConverter
import logging

LOG = logging.getLogger(__name__)


# FIXME: probably need an additional widget traverser to inline
#        validate param_groups fields
class ExperimentParamGroup(AutoFields, Group):

    parameters = None

    def getContent(self):
        if hasattr(self.context, 'parameters'):
            # TODO: do better check here?
            # add form context should not have any parameters field
            # edit form should have
            self.parameters = self.context.parameters
        if self.parameters is None:
            # TODO: check assumption here
            # assume that we have an add form and need a fresh dict?
            self.parameters = {}
        if self.toolkit not in self.parameters:
            self.parameters[self.toolkit] = {}
        return self.parameters[self.toolkit]

    def update(self):
        # FIXME: stupid autoform thinks if the schema is in schema
        #        attribute and not in additionalSchemata it won't need a
        #        prefix
        # self.updateFieldsFromSchemata()
        #
        # stupid autoform thinks self.groups should be a list and not a tuple
        # :(
        self.groups = list(self.groups)
        # use  processFields instead
        # , permissionChecks=have_user)
        processFields(self, self.schema, prefix=self.toolkit)
        # revert back to tuple
        self.groups = tuple(self.groups)

        super(ExperimentParamGroup, self).update()


class ParamGroupMixin(object):
    """
    Mix-in to handle parameter froms
    """

    param_groups = None

    def addToolkitFields(self):
        # FIXME: This relies on the order the vocabularies are returned, which
        # shall be fixed.
        vocab = getUtility(
            IVocabularyFactory,
            "org.bccvl.site.algorithm_category_vocab")(self.context)
        groups = OrderedDict((cat.value, [])
                             for cat in chain((SimpleTerm(None),), vocab))

        # TODO: only sdms have functions at the moment ,... maybe sptraits as
        # well?
        func_vocab = getUtility(IVocabularyFactory, name=self.func_vocab_name)
        functions = getattr(self.context, self.func_select_field, None) or ()


        # TODO: could also use uuidToObject(term.value) instead of relying on
        # BrainsVocabluary terms
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
            # param_group.prefix = ''+ form.prefix?
            param_group.toolkit = toolkit.UID()
            param_group.schema = parameters_schema
            # param_group.prefix = "{}{}.".format(self.prefix, toolkit.id)
            # param_group.fields = Fields(parameters_schema, prefix=toolkit.id)
            param_group.label = u"configuration for {}".format(toolkit.title)
            if len(parameters_schema.names()) == 0:
                param_group.description = u"No configuration options"
            groups[toolkit.algorithm_category].append(param_group)

        # join the lists in that order
        self.param_groups = {
            self.func_select_field: (tuple(groups[None])
                                     + tuple(groups['profile'])
                                     + tuple(groups['machineLearning'])
                                     + tuple(groups['statistical'])
                                     + tuple(groups['geographic']))
        }

    def updateFields(self):
        super(ParamGroupMixin, self).updateFields()
        self.addToolkitFields()

    def updateWidgets(self):
        super(ParamGroupMixin, self).updateWidgets()
        # update groups here
        uuid = self.request.get('uuid')
        expobj = None
        if uuid:
            expobj = uuidToObject(uuid)
        for group in self.param_groups[self.func_select_field]:
            try:
                group.update()

                # copy algorithm group parameters from the specified SDM experiment if any
                if not expobj or group.toolkit not in expobj.parameters:
                    continue

                # There are 3 groups of algorithm parameters: invisible, pseudo absence, and others.
                # Copy parameters from the pseudo absence, and others only.
                exp_params = expobj.parameters.get(group.toolkit, {})
                for param_group in group.groups:
                    for name in tuple(param_group.widgets):
                        pname = name.split(group.toolkit + '.')[1]
                        if pname in exp_params:
                            conv = getMultiAdapter((param_group.fields[name].field, param_group.widgets[name]), IDataConverter)
                            param_group.widgets[name].value = conv.toWidgetValue(exp_params.get(pname))
            except Exception as e:
                LOG.info("Group %s failed: %s", group.__name__, e)
        # should group generation happen here in updateFields or in update?

    def extractData(self, setErrors=True):
        data, errors = super(ParamGroupMixin, self).extractData(setErrors)
        for group in self.param_groups[self.func_select_field]:
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
        for group in self.param_groups[self.func_select_field]:
            if self.is_toolkit_selected(group.toolkit, data[self.func_select_field]):
                group.applyChanges(data)
                new_params[group.toolkit] = group.getContent()
        self.context.parameters = new_params

        return changed


class MultiParamGroupMixin(object):
    """
    Mix-in to handle multiple parameter froms
    """

    param_groups = None

    def addToolkitFields(self):
        self.param_groups = {}
        for func_vocab_name, func_select_field in zip(self.func_vocab_name, self.func_select_field):
            param_groups = self._addToolkitFields(
                func_vocab_name, func_select_field)
            self.param_groups[func_select_field] = param_groups

    def _addToolkitFields(self, func_vocab_name, func_select_field):
        # section ... algorithm section
        # FIXME: This relies on the order the vicabularies are returned, which
        # shall be fixed.
        vocab = getUtility(
            IVocabularyFactory, "org.bccvl.site.algorithm_category_vocab")(self.context)
        groups = OrderedDict((cat.value, [])
                             for cat in chain((SimpleTerm(None),), vocab))

        # TODO: only sdms have functions at the moment ,... maybe sptraits as
        # well?
        func_vocab = getUtility(IVocabularyFactory, name=func_vocab_name)
        functions = getattr(self.context, func_select_field, None) or ()

        # TODO: could also use uuidToObject(term.value) instead of relying on
        # BrainsVocabluary terms
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
            # param_group.prefix = ''+ form.prefix?
            param_group.toolkit = toolkit.UID()
            param_group.schema = parameters_schema
            # param_group.prefix = "{}{}.".format(self.prefix, toolkit.id)
            # param_group.fields = Fields(parameters_schema, prefix=toolkit.id)
            param_group.label = u"configuration for {}".format(toolkit.title)
            if len(parameters_schema.names()) == 0:
                param_group.description = u"No configuration options"
            groups[toolkit.algorithm_category].append(param_group)

        # join the lists in that order
        return (tuple(groups[None]) +
                tuple(groups['profile']) +
                tuple(groups['machineLearning']) +
                tuple(groups['statistical']) +
                tuple(groups['geographic']))

    def updateFields(self):
        super(MultiParamGroupMixin, self).updateFields()
        self.addToolkitFields()

    def updateWidgets(self):
        super(MultiParamGroupMixin, self).updateWidgets()

        # Copy parameters from an experiment selected if any
        uuid = self.request.get('uuid')
        expobj = None
        if uuid:
            expobj = uuidToObject(uuid)

        # update groups here
        for group in (g for groups in self.param_groups.values() for g in groups):
            try:
                group.update()

                # copy algorithm group parameters from the specified SDM experiment if any
                if not expobj or group.toolkit not in expobj.parameters:
                    continue

                # There are 3 groups of algorithm parameters: invisible, pseudo absence, and others.
                # Copy parameters from the pseudo absence, and others only.
                exp_params = expobj.parameters.get(group.toolkit, {})
                for param_group in group.groups:
                    for name in tuple(param_group.widgets):
                        pname = name.split(group.toolkit + '.')[1]
                        if pname in exp_params:
                            conv = getMultiAdapter((param_group.fields[name].field, param_group.widgets[name]), IDataConverter)
                            param_group.widgets[name].value = conv.toWidgetValue(exp_params.get(pname))

            except Exception as e:
                LOG.info("Group %s failed: %s", group.__name__, e)
        # should group generation happen here in updateFields or in update?

    def extractData(self, setErrors=True):
        data, errors = super(MultiParamGroupMixin, self).extractData(setErrors)
        for group in (g for groups in self.param_groups.values() for g in groups):
            groupData, groupErrors = group.extractData(setErrors=setErrors)
            data.update(groupData)
            if groupErrors:
                if errors:
                    errors += groupErrors
                else:
                    errors = groupErrors
        return data, errors

    def applyChanges(self, data):
        changed = super(MultiParamGroupMixin, self).applyChanges(data)
        # apply algo params:
        new_params = {}
        for field, groups in self.param_groups.items():
            for group in groups:
                if self.is_toolkit_selected(group.toolkit, data[field]):
                    group.applyChanges(data)
                    new_params[group.toolkit] = group.getContent()
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
        return IExperimentJobTracker(self.context).state

    # condition=lambda form: form.showApply)
    @button.buttonAndHandler(u'Start Job')
    def handleStartJob(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        msgtype, msg = IExperimentJobTracker(
            self.context).start_job(self.request)
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
        jt = IExperimentJobTracker(obj)
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

    def updateWidgets(self):
        super(Add, self).updateWidgets()

        # Pre-fill widget fields with field values from the specified SDM.
        uuid = self.request.get('uuid')
        if uuid:
            expobj = uuidToObject(uuid)
            self.widgets["IDublinCore.title"].value = expobj.title
            self.widgets["IDublinCore.description"].value = expobj.description
            for name in self.widgets.keys():
                if name not in ["IDublinCore.title", "IDublinCore.description"]:
                    conv = getMultiAdapter((self.fields[name].field, self.widgets[name]), IDataConverter)
                    self.widgets[name].value = conv.toWidgetValue(getattr(expobj, name))


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
        # we'll have to override it to find a place to apply our algo_group
        # data'
        newob = super(SDMAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data
        # on read
        new_params = {}
        for group in self.param_groups[self.func_select_field]:
            if group.toolkit in data['functions']:
                group.applyChanges(data)
                new_params[group.toolkit] = group.getContent()
        newob.parameters = new_params
        IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # data contains already field values
        datasets = data.get('environmental_datasets', {}).keys()
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide
            # error
            raise ActionExecutionError(
                Invalid('No environmental dataset selected.'))

        # Determine highest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        res_vocab = getUtility(
            IVocabularyFactory, 'resolution_source')(self.context)
        if data.get('scale_down', False):
            # ... find highest resolution
            resolution_idx = 99  # Arbitrary choice of upper index limit
            for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
                idx = res_vocab._terms.index(
                    res_vocab.getTerm(dsbrain.BCCResolution))
                if idx < resolution_idx:
                    resolution_idx = idx
            data['resolution'] = res_vocab._terms[resolution_idx].value
        else:
            # ... find lowest resolution
            resolution_idx = -1
            for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
                idx = res_vocab._terms.index(
                    res_vocab.getTerm(dsbrain.BCCResolution))
                if idx > resolution_idx:
                    resolution_idx = idx
            data['resolution'] = res_vocab._terms[resolution_idx].value


class MSDMAdd(ParamGroupMixin, Add):
    """
    Add MSDM Experiment
    """

    portal_type = "org.bccvl.content.msdmexperiment"

    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'function'

    def is_toolkit_selected(self, tid, data):
        return tid in data

    def create(self, data):
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group
        # data'
        newob = super(MSDMAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data
        # on read
        new_params = {}
        for group in self.param_groups[self.func_select_field]:
            if group.toolkit == data['function']:
                group.applyChanges(data)
                new_params[group.toolkit] = group.getContent()
        newob.parameters = new_params
        IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # data contains already field values
        datasets = data.get('environmental_datasets', {}).keys()
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide
            # error
            raise ActionExecutionError(
                Invalid('No environmental dataset selected.'))

        # Determine highest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        res_vocab = getUtility(
            IVocabularyFactory, 'resolution_source')(self.context)
        if data.get('scale_down', False):
            # ... find highest resolution
            resolution_idx = 99  # Arbitrary choice of upper index limit
            for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
                idx = res_vocab._terms.index(
                    res_vocab.getTerm(dsbrain.BCCResolution))
                if idx < resolution_idx:
                    resolution_idx = idx
            data['resolution'] = res_vocab._terms[resolution_idx].value
        else:
            # ... find lowest resolution
            resolution_idx = -1
            for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
                idx = res_vocab._terms.index(
                    res_vocab.getTerm(dsbrain.BCCResolution))
                if idx > resolution_idx:
                    resolution_idx = idx
            data['resolution'] = res_vocab._terms[resolution_idx].value


class MSDMView(ParamGroupMixin, View):
    """
    View MSDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'function'

    def is_toolkit_selected(self, tid, data):
        return tid in data


class MMEAdd(ParamGroupMixin, Add):
    """
    Add Migratory Modelling Experiment
    """

    portal_type = "org.bccvl.content.mmexperiment"

    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'function'

    def is_toolkit_selected(self, tid, data):
        return tid in data

    def create(self, data):
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group
        # data'
        newob = super(MMEAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data
        # on read
        new_params = {}
        for group in self.param_groups[self.func_select_field]:
            if group.toolkit == data['function']:
                group.applyChanges(data)
                new_params[group.toolkit] = group.getContent()
        newob.parameters = new_params
        #IBCCVLMetadata(newob)['resolution'] = data['resolution']
        return newob

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # data contains already field values
        datasets = data.get('datasubsets', [])
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide
            # error
            raise ActionExecutionError(
                Invalid('No environmental dataset selected.'))

        # Determine highest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        # res_vocab = getUtility(
        #     IVocabularyFactory, 'resolution_source')(self.context)
        # if data.get('scale_down', False):
        #     # ... find highest resolution
        #     resolution_idx = 99  # Arbitrary choice of upper index limit
        #     for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
        #         idx = res_vocab._terms.index(
        #             res_vocab.getTerm(dsbrain.BCCResolution))
        #         if idx < resolution_idx:
        #             resolution_idx = idx
        #     data['resolution'] = res_vocab._terms[resolution_idx].value
        # else:
        #     # ... find lowest resolution
        #     resolution_idx = -1
        #     for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
        #         idx = res_vocab._terms.index(
        #             res_vocab.getTerm(dsbrain.BCCResolution))
        #         if idx > resolution_idx:
        #             resolution_idx = idx
        #     data['resolution'] = res_vocab._terms[resolution_idx].value


class MMEView(ParamGroupMixin, View):
    """
    View MME Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = 'sdm_functions_source'
    func_select_field = 'function'

    def is_toolkit_selected(self, tid, data):
        return tid in data


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
            # FIXME: Make this a widget error, currently shown as form wide
            # error
            raise ActionExecutionError(
                Invalid('No future climate dataset selected.'))
        models = data.get('species_distribution_models', {})
        if not tuple(chain.from_iterable(x for x in models.values())):
            # FIXME: collecting all errors is better than raising an exception for each single error
            # TODO: see
            # http://stackoverflow.com/questions/13040487/how-to-raise-a-widgetactionexecutionerror-for-multiple-fields-with-z3cform
            raise WidgetActionExecutionError(
                'species_distribution_models',
                Invalid('No source dataset selected.')
            )

        # Determine lowest resolution
        # FIXME: this is slow and needs improvements
        #        and accessing _terms is not ideal
        res_vocab = getUtility(
            IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            # FIXME: vocabulary lookup may fail if there is no resolution or
            # resolution is undefined (LookupError in getTerm)
            idx = res_vocab._terms.index(
                res_vocab.getTerm(dsbrain.BCCResolution))
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
            raise WidgetActionExecutionError(
                'projection',
                Invalid('No projection dataset selected.')
            )
        # check if threshold values are in range
        for dataset in (x for x in datasets.values()):
            if not dataset:
                raise WidgetActionExecutionError(
                    'projection',
                    Invalid('Please select at least one dataset within experiment'))
            # key: {label, value}
            dsuuid = dataset.keys()[0]
            ds = uuidToObject(dsuuid)
            value = dataset[dsuuid]['value']
            md = IBCCVLMetadata(ds)
            # ds should be a projection output which has only one layer
            # FIXME: error message is not clear enough and
            #        use widget.errors instead of exception
            # also it will only verify if dateset has min/max values in
            # metadata
            layermd = md['layers'].values()[0]
            if 'min' in layermd and 'max' in layermd:
                # FIXME: at least layermd['min'] may be a string '0', when
                # comparing to decimal from threshold selector, this comparison
                # fails and raises the widget validation error
                if value <= float(layermd['min']) or value >= float(layermd['max']):
                    raise WidgetActionExecutionError(
                        'projection',
                        Invalid('Selected threshold is out of range'))


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
            # FIXME: Make this a widget error, currently shown as form wide
            # error
            raise ActionExecutionError(Invalid('No dataset selected.'))

        # all selected datasets are combined into one ensemble analysis
        # get resolution for ensembling
        # Determine lowest resolution
        # FIXME: An experiment should store the resolution metadata on the dataset
        # e.g. an SDM current projection needs to store resolution on tif file
        res_vocab = getUtility(
            IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            try:
                idx = res_vocab._terms.index(
                    res_vocab.getTerm(dsbrain.BCCResolution))
            except:
                # FIXME: need faster way to order resolutions
                idx = res_vocab._terms.index(res_vocab.getTerm(
                    dsbrain.getObject().__parent__.job_params['resolution']))
            if idx > resolution_idx:
                resolution_idx = idx
        data['resolution'] = res_vocab._terms[resolution_idx].value


class SpeciesTraitsView(MultiParamGroupMixin, View):
    """
    View SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = ('traits_functions_species_source',
                       'traits_functions_diff_source')
    func_select_field = ('algorithms_species', 'algorithms_diff')

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid in data


class SpeciesTraitsEdit(MultiParamGroupMixin, Edit):
    """
    Edit SDM Experiment
    """
    # Parameters for ParamGroupMixin
    func_vocab_name = ('traits_functions_species_source',
                       'traits_functions_diff_source')
    func_select_field = ('algorithms_species', 'algorithms_diff')

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid in data


class SpeciesTraitsAdd(MultiParamGroupMixin, Add):
    portal_type = "org.bccvl.content.speciestraitsexperiment"

    # Parameters for ParamGroupMixin
    func_vocab_name = ('traits_functions_species_source',
                       'traits_functions_diff_source')
    func_select_field = ('algorithms_species', 'algorithms_diff')

    # override is_toolkit_selected
    def is_toolkit_selected(self, tid, data):
        return tid in data

    def create(self, data):
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group
        # data'
        newob = super(SpeciesTraitsAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data
        # on read
        new_params = {}
        for field, groups in self.param_groups.items():
            for group in groups:
                if group.toolkit in data[field]:
                    group.applyChanges(data)
                    new_params[group.toolkit] = group.getContent()
        newob.parameters = new_params
        return newob

    def validateAction(self, data):
        # TODO: check data ...
        pass
