from plone.directives import dexterity
from z3c.form import button
from z3c.form.form import extends, applyChanges
from z3c.form.interfaces import ActionExecutionError, IErrorViewSnippet
from org.bccvl.site.interfaces import IJobTracker
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.dexterity.browser import add, edit
from org.bccvl.site import MessageFactory as _
from org.bccvl.site.api.dataset import getdsmetadata
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
        func_vocab = getUtility(IVocabularyFactory, name='sdm_functions_source')
        functions = getattr(self.context, 'functions', None) or ()
        # TODO: could also use uuidToObject(term.value) instead of relying on BrainsVocabluary terms
        for toolkit in (term.brain.getObject() for term in func_vocab(self.context)):
            if self.mode == DISPLAY_MODE and toolkit.UID() not in functions:
                # filter out unused algorithms in display mode
                continue
            # FIXME: need to cache
            try:
                # FIXME: do some caching here
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
        # FIXME: store only selected algos
        changed = super(ParamGroupMixin, self).applyChanges(data)
        # apply algo params:
        new_params = {}
        for group in self.param_groups:
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

    extends(dexterity.DisplayForm)

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

    # def render(self):
    #     '''See interfaces.IForm'''
    #     # render content template
    #     import zope.component
    #     from zope.pagetemplate.interfaces import IPageTemplate

    #     if self.template is None:
    #         template = zope.component.getMultiAdapter((self, self.request),
    #             IPageTemplate)
    #         return template(self)
    #     return self.template()

       # super does not work... expects different kind of template
        # return super(View,  self).render()
    #     template = getattr(self, 'template', None)
    #     if template is not None:
    #         return self.template.render(self)
    #     return zope.publisher.publish.mapply(self.render, (), self.request)
    # render.base_method = True


class SDMView(ParamGroupMixin, View):
    """
    View SDM Experiment
    """

    pass


class Edit(edit.DefaultEditForm):
    """
    Edit Experiment
    """

    pass


class SDMEdit(ParamGroupMixin, Edit):
    """
    Edit SDM Experiment
    """

    template = ViewPageTemplateFile("experiment_edit.pt")


class Add(add.DefaultAddForm):
    """
    Add Experiment
    """

    extends(dexterity.DisplayForm,
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

    def create(self, data):
        # FIXME: store only selcted algos
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group data'
        newob = super(SDMAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data on read
        new_params = {}
        for group in self.param_groups:
            content = group.getContent()
            applyChanges(group, content, data)
            new_params[group.toolkit] = content
        newob.parameters = new_params
        return newob

    # TODO: deprecate once data mover/manager API is finished?
    template = ViewPageTemplateFile("experiment_add.pt")

    # TODO: is this still necessary?
    def occurrences_mapping(self):

        def _add_ds_to_map(vocab, map):
            # TODO: relies on BrainsVocabulary terms
            for brain in (term.brain for term in vocab):
                dataset_info = getdsmetadata(brain.getObject())

                mapping[dataset_info['vizurl']] = {
                    'object': dataset_info['url'],
                    'file': dataset_info['file'],
                }

                if 'vizurl' in dataset_info:
                    mapping[dataset_info['vizurl']].update({
                        'vizurl': dataset_info['vizurl']
                    })

        import json
        occur_vocab = getUtility(IVocabularyFactory, 'species_presence_datasets_vocab')(self.context)
        abs_vocab = getUtility(IVocabularyFactory, 'species_absence_datasets_vocab')(self.context)

        mapping = dict()
        _add_ds_to_map(occur_vocab, mapping)
        _add_ds_to_map(abs_vocab, mapping)

        # FIXME: this does look bad, and should probably be handled by a proper widget
        js_tmpl = """
            window.bccvl || (window.bccvl = {});
            window.bccvl.lookups || (window.bccvl.lookups = {});
            window.bccvl.lookups.occurrencesMap = %s;
        """
        return js_tmpl % json.dumps(mapping)

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # data contains already field values
        resolution = None
        datasets = data.get('environmental_datasets', {}).keys()
        if not datasets:
            # FIXME: Make this a widget error, currently shown as form wide error
            raise ActionExecutionError(Invalid('No environmental dataset selected'))
        # FIXME: index resolution for faster access
        #        or use dsbrain.subjecturi to get info
        #        or run sparql query across all dsbrain.subjecturis
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            if resolution is None:
                resolution = dsbrain.BCCResolution
                continue
            if dsbrain.BCCResolution != resolution:
                # FIXME: Make this a widget error, currently shown as form wide error
                raise ActionExecutionError(Invalid("All datasets must have the same resolution"))


class ProjectionAdd(Add):

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # FIXME: do spatial scale validation as well (find_projection
        #       might be able to do it already)
        # FIXME: when changing source model, adapt resolution
        #        allow only from same resolution
        #        find projection for this resolution
        #        validate resolution on submit
        #        check that layers in sdm match layers in future data (can this be a partial match as well?)

        # FIXME: get rid of this as soon as UI supports it
        # check if we have a resolution in the request and set it to
        # whatever the sdm has if not there
        resolution = data.get("resolution")
        if resolution is None:
            uuids = data.get('species_distribution_models')
            from plone.app.uuid.utils import uuidToCatalogBrain
            from gu.z3cform.rdf.interfaces import IResource
            from org.bccvl.site.namespace import BCCPROP
            for sdm in (uuidToCatalogBrain(uuid) for uuid in uuids):
                sdmgraph = IResource(sdm)
                resolution = sdmgraph.value(BCCPROP['resolution'])
                # TODO: looks just at first sdm, but should also validate
                #       tha they have all the same resolution
                data['resolution'] = resolution.identifier
                break

        from org.bccvl.site.api.dataset import find_projections
        result = find_projections(self.context, data.get('emission_scenarios'),
                                  data.get('climate_models'),
                                  data.get('years'))
        if not len(result):
            raise ActionExecutionError(Invalid(u"The combination of projection points does not match any datasets"))


class BiodiverseAdd(Add):

    def create(self, data):
        # FIXME: store only selcted algos
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group data'
        newob = super(BiodiverseAdd, self).create(data)
        # and now apply data['projection']
        newob.projection = data['projection']
        return newob

    def validateAction(self, data):
        # TODO: check data ...
        pass

    def extractData(self, setErrors=True):
        data, errors = super(BiodiverseAdd, self).extractData(setErrors)
        # extract datasets and thresholds and convert to field values
        prefix = '{}{}{}'.format(self.prefix, self.widgets.prefix, 'projection')
        count = self.request.get('{}.count'.format(prefix))
        try:
            count = int(count)
            projdata = []
            for x in xrange(count):
                dsname = '{}.{}.dataset'.format(prefix, x)
                thname = '{}.{}.threshold'.format(prefix, x)
                # try to parse value as float... parsing as Decimal throws an unsupported error
                _ = float(self.request.get(thname))
                # FIXME: may raise TypeError ... not caught below
                projdata.append({'dataset': self.request.get(dsname),
                                 'threshold': Decimal(self.request.get(thname))})
            if not projdata:
                # TODO: set errors
                pass
            data['projection'] = projdata
        except (Invalid, ValueError, MultipleErrors) as error:
            #view = getMultiAdapter((error, self.request, widget, widget.field,
            view = getMultiAdapter((error, self.request, None, None,
                                    self.form, self.content), IErrorViewSnippet)
            view.update()
            # if self.setErrors:
            #     widget.error = view
            errors += (view, )
        else:
            data['projection'] = projdata
        return data, errors


class ProjectionAddView(add.DefaultAddView):
    """
    The formwrapper wrapping Add form above
    """

    form = ProjectionAdd


class SDMAddView(add.DefaultAddView):

    form = SDMAdd


class BiodiverseAddView(add.DefaultAddView):

    form = BiodiverseAdd


class EnsembleAdd(Add):

    def validateAction(self, data):
        # TODO: check data ...
        pass


class EnsembleAddView(add.DefaultAddView):

    form = EnsembleAdd


class SpeciesTraitsAdd(Add):

    # TODO: almost same as in SDMAdd
    def create(self, data):
        # FIXME: store only selcted algos
        # Dexterity base AddForm bypasses self.applyData and uses form.applyData directly,
        # we'll have to override it to find a place to apply our algo_group data'
        newob = super(SpeciesTraitsAdd, self).create(data)
        # apply values to algo dict manually to make sure we don't write data on read
        new_params = {}
        for group in self.param_groups:
            content = group.getContent()
            applyChanges(group, content, data)
            new_params[group.toolkit] = content
        newob.parameters = new_params
        return newob

    # TODO: deprecate once data mover/manager API is finished?
    template = ViewPageTemplateFile("experiment_add.pt")

    def validateAction(self, data):
        # TODO: check data ...
        pass

    # TODO: all below here is almost like ParmsGroupMixin ->merge
    param_groups = ()

    occurrences_mapping = u""

    def addAlgorithmFields(self):
        groups = []
        # TODO: only sdms have functions at the moment ,... maybe sptraits as well?
        func_vocab = getUtility(IVocabularyFactory, name='traits_functions_source')
        algorithm = getattr(self.context, 'algorithm', None) or ()
        for toolkit in (term.brain.getObject() for term in func_vocab(self.context)):
            if self.mode == DISPLAY_MODE and toolkit.UID() != algorithm:
                # filter out unused algorithms in display mode
                continue
            # FIXME: need to cache
            try:
                # FIXME: do some caching here
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
        super(SpeciesTraitsAdd, self).updateFields()
        self.addAlgorithmFields()

    def updateWidgets(self):
        super(SpeciesTraitsAdd, self).updateWidgets()
        # update groups here
        for group in self.param_groups:
            try:
                group.update()
            except Exception as e:
                LOG.info("Group %s failed: %s", group.__name__, e)
        # should group generation happen here in updateFields or in update?

    def extractData(self, setErrors=True):
        data, errors = super(SpeciesTraitsAdd, self).extractData(setErrors)
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
        # FIXME: store only selected algos
        changed = super(SpeciesTraitsAdd, self).applyChanges(data)
        # apply algo params:
        new_params = {}
        for group in self.param_groups:
            content = group.getContent()
            param_changed = applyChanges(group, content, data)
            new_params[group.toolkit] = content
        self.context.parameters = new_params

        return changed


class SpeciesTraitsAddView(add.DefaultAddView):

    form = SpeciesTraitsAdd
