
// namespace dictionary to hold all bccvl specific code / widgets
var bccvl = {};

(

    // TODO: there may be a problem here with various element ids. These widgets may produce/rely on
    //       duplicate id's in the dom.
    function($) {

        // helper function for selectable behaviour
        function selectable($elements) {
            $elements.click(function(event) {
                // get parent row div
                var $row = $(event.target).closest('div.row');
                // get input element (radio / checkbox)
                var $input = $row.find('input');
                // new state for input element
                if (! $input.is(event.target)) {
                    // if click was on input element checked state
                    // has already been set
                    var setchecked = ! $input.prop('checked');
                    // apply new state
                    $input.prop('checked', setchecked);
                };
                // update row class according to new checked state
                $row.parent().find('div.row:has(input:checked)').addClass("ui-selected");
                $row.parent().find('div.row:has(input:not(:checked))').removeClass("ui-selected");
            });
        }

        // single/multi select dataset widget
        bccvl.select_dataset = function($element, options) {

            // required options: field, genre

            var settings = $.extend({
                // These are the defaults.
                target: '#' + options.field + '-modal',
                remote: 'datasets_listing_popup', // modal box id
                widgetname: 'form.widgets.' + options.field,
                widgetid: 'form-widgets-' + options.field,
                widgeturl: location.origin + location.pathname + '/++widget++' + options.field, // used to reload entire widget
                widgetelement: 'div.selecteditem',
                result_selector: '#datasets-popup-result',
                result_child_selector: '#datasets-popup-result-list',
                filters: ['text', 'source'],
                experimenttype: undefined
            }, options );

            // variable names that make more sense
            var $modal = $(settings.target);
            // move $modal to top level body element to avoid nested form elements
            $modal.prependTo($('body'));

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [{name: 'datasets.multiple',
                                  value: settings.multiple}];
                $.each(settings.filters, function(index, value) {
                    paramlist.push({name: 'datasets.filters:list',
                                    value: value});
                });
                $.each(settings.genre, function(index, value) {
                    paramlist.push({name: 'datasets.filter.genre:list',
                                    value: value});
                });
                if (settings.experimenttype) {
                    paramlist.push({name: 'datasets.filter.experimenttype:list',
                                    value: settings.experimenttype});
                }
                // bootstrap 2 modal does'n have loaded event so we have to do it ourselves
                $modal.modal('show')
                    .find('.modal-body')
                    .load(settings.remote + '?' + $.param(paramlist), function() {
                        bind_events_on_modal_content();
                    });
            });

            function load_search_results(url, params) {
                $modal.find(settings.result_selector).load(
                    url + ' ' + settings.result_child_selector, params,
                    // reapply select events
                    function() {
                        selectable($modal.find(settings.result_child_selector));
                        // intercept pagination links
                        $modal.find('div.listingBar a').click( function(event) {
                            event.preventDefault();
                            load_search_results($(this).attr('href'));
                        });
                    }
                );
            };

            // initialise modal when finished loading
            function bind_events_on_modal_content() {
                // hookup events within modal
                $modal.find('form').submit(function(event) {
                    event.preventDefault();
                    load_search_results(
                        $(this).attr('action'),
                        $(this).serialize()
                    );
                });
                // select on first load
                selectable($modal.find(settings.result_child_selector));
                // intercept pagination links
                $modal.find('div.listingBar a').click( function(event) {
                    event.preventDefault();
                    load_search_results($(this).attr('href'));
                });
            };

            // clear modal on close
            $modal.on('hidden', function() {
                $(this).removeData('modal');
                $(this).find('.modal-body').empty();
            });

            // when user preses 'save' button in modal
            $modal.find('button.btn-primary').click(function(event) {
                event.preventDefault();
                // get selected element
                var $selected = $modal.find('.ui-selected');
                var uuid = $selected.map(function() { return $(this).attr('data-uuid'); }).get();
                // we have all the data we need so get rid of the modal
                $modal.modal('hide');
                if ($selected.length) {
                    // fetch html for widget
                    var params = [];
                    $.each(uuid, function(index, value){
                        params.push({name: settings.widgetname, value: value});
                    });
                    $('#' + settings.widgetid + '-selected').load(
                        settings.widgeturl + ' ' + settings.widgetelement,
                        params,
                        function(text, status, xhr) {
                            // trigger change event when widget has been updated
                            $(this).trigger('widgetChanged');
                        }

                    );
                }
            });

            $('#' + settings.widgetid + '-selected').on('click', 'a:has(i.icon-remove)',
                function(event){
                    event.preventDefault();
                    $(this).parents('div.selecteditem').remove();
                    // trigger change event on widget update
                    $(event.delegateTarget).trigger('widgetChanged');
                }
            );

        };

        // TODO: differences to widget above:
        //    - the way paramlist is being built different initialisation
        //    - parameter list on select  layers button


        bccvl.select_dataset_layers = function($element, options) {

            // required options: field, genre, multiple

            var settings = $.extend({
                // These are the defaults.
                target: '#' + options.field + '-modal',
                remote: 'datasets_listing_popup',
                widgetname: 'form.widgets.' + options.field,
                widgetid: 'form-widgets-' + options.field,
                widgeturl: location.origin + location.pathname + '/++widget++' + options.field,
                widgetelement: 'div.selecteditem',
                result_selector: '#datasets-popup-result',
                result_child_selector: '#datasets-popup-result-list',
                filters: ['text', 'source', 'layer', 'resolution'],
                multiple: 'multiple'
            }, options );

            // variable names that make more sense
            var $modal = $(settings.target);
            // move $modal to top level body element to avoid nested form elements
            $modal.prependTo($('body'));

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [{name: 'datasets.multiple',
                                  value: settings.multiple}];
                $.each(settings.filters, function(index, value) {
                    paramlist.push({name: 'datasets.filters:list',
                                    value: value});
                });
                $.each(settings.genre, function(index, value) {
                    paramlist.push({name: 'datasets.filter.genre:list',
                                    value: value});
                });
                // bootstrap 2 modal does'n have loaded event so we have to do it ourselves
                $modal.modal('show')
                    .find('.modal-body')
                    .load(settings.remote + '?' + $.param(paramlist), function() {
                        bind_events_on_modal_content();
                    });
            });

            function load_search_results(url, params) {
                $modal.find(settings.result_selector).load(
                    url + ' ' + settings.result_child_selector, params,
                    // reapply single select events
                    function() {
                        selectable($modal.find(settings.result_child_selector));
                        // intercept pagination links
                        $modal.find('div.listingBar a').click( function(event) {
                            event.preventDefault();
                            load_search_results($(this).attr('href'));
                        });
                    }
                );
            };

            // initialise modal when finished loading
            function bind_events_on_modal_content() {
                // hookup events within modal
                $modal.find('form').submit(function(event) {
                    event.preventDefault();
                    load_search_results(
                        $(this).attr('action'),
                        $(this).serialize()
                    );
                });
                // enable selectable
                selectable($modal.find(settings.result_child_selector));
                // intercept pagination links
                $modal.find('div.listingBar a').click( function(event) {
                    event.preventDefault();
                    load_search_results($(this).attr('href'));
                });
            };

            // clear modal on close
            $modal.on('hidden', function() {
                $(this).removeData('modal');
                $(this).find('.modal-body').empty();
            });

            // when user preses 'save' button in modal
            // TODO: we should rather check for all input elements instead of complex jq selectors? (same for single select)
            $modal.find('button.btn-primary').click(function(event) {
                event.preventDefault();
                // get selected element
                var $selected = $modal.find('.ui-selected');
                var uuid = $selected.map(function() {
                    return {uuid: $(this).attr('data-uuid'),
                            layer: $(this).attr('data-layer')};
                }).get();
                // we have all the data we need so get rid of the modal
                $modal.modal('hide');
                if ($selected.length) {
                    // we only change things if there was a selection
                    var params = [];
                    // collect all existing datasets and layers
                    var $cursel = $('input[name^="' + settings.widgetname + '.dataset"]');
                    var count = 0;
                    $.each($cursel, function(index, dsinput) {
                        var $layer = $('input[name="' + $(dsinput).attr('name').replace(/\.dataset\./, '.layer.') + '"]');
                        params.push({name: settings.widgetname + '.dataset.' + count,
                                     value: $(dsinput).val()});
                        params.push({name: settings.widgetname + '.layer.' + count,
                                     value: $layer.val()});
                        count += 1;
                    });
                    // collect newly selected layers
                    $.each(uuid, function(index, value){
                        params.push({name: settings.widgetname + '.dataset.' + count,
                                     value: value.uuid});
                        params.push({name: settings.widgetname + '.layer.' + count,
                                     value: value.layer});
                        count += 1;
                    });
                    // add count parameter
                    params.push({name: settings.widgetname + '.count', value: count});
                    // fetch html for widget
                    $('#' + settings.widgetid + '-selected').load(
                        settings.widgeturl + ' ' + settings.widgetelement,
                        params,
                        function(text, status, xhr) {
                            // trigger change event on widget update
                            $(this).trigger('widgetChanged');
                        }
                    );
                }
            });

            $('#' + settings.widgetid + '-selected').on('click', 'a:has(i.icon-remove)',
                function(event){
                    event.preventDefault();
                    $(this).parents('div.selecteditem').remove();
                    // trigger change event on widget update
                    $(event.delegateTarget).trigger('widgetChanged');
                }
            );

        };


        // TODO: below is a modified copy of bccvl.select_dataset, ideally these sholud be merged into one
        //       -> needs better ajax param processing. (maybe via hidden input fields?)

        // single/multi select dataset widget
        bccvl.select_dataset_future = function($element, options) {

            // TODO: on init fetch settings.params from other widget

            // required options: field, genre

            var settings = $.extend({
                // These are the defaults.
                target: '#' + options.field + '-modal',
                remote: 'datasets_listing_popup', // modal box id
                widgetname: 'form.widgets.' + options.field,
                widgetid: 'form-widgets-' + options.field,
                widgeturl: location.origin + location.pathname + '/++widget++' + options.field, // used to reload entire widget
                widgetelement: 'div.selecteditem',
                result_selector: '#datasets-popup-result',
                result_child_selector: '#datasets-popup-result-list',
                filters: ['text', 'source', 'resolution', 'emsc', 'gcm'],
                multiple: 'multiple'
            }, options );

            // variable names that make more sense
            var $modal = $(settings.target);
            // move $modal to top level body element to avoid nested form elements
            $modal.prependTo($('body'));

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [{name: 'datasets.multiple',
                                  value: settings.multiple}];
                $.each(settings.filters, function(index, value) {
                    paramlist.push({name: 'datasets.filters:list',
                                    value: value});
                });
                $.each(settings.genre, function(index, value) {
                    paramlist.push({name: 'datasets.filter.genre:list',
                                    value: value});
                });
                // add resolution parameter
                paramlist.push({name: 'datasets.filter.resolution:list',
                                value: settings.params.resolution});
                // add layers filter
                $.each(settings.params.layers, function(index, value) {
                    paramlist.push({name: 'datasets.filter.layer:list',
                                    value: value});
                });

                // bootstrap 2 modal does'n have loaded event so we have to do it ourselves
                $modal.modal('show')
                    .find('.modal-body')
                    .load(settings.remote + '?' + $.param(paramlist), function() {
                        bind_events_on_modal_content();
                    });
            });

            function load_search_results(url, params) {
                $modal.find(settings.result_selector).load(
                    url + ' ' + settings.result_child_selector, params,
                    // reapply select events
                    function() {
                        selectable($modal.find(settings.result_child_selector));
                        // intercept pagination links
                        $modal.find('div.listingBar a').click( function(event) {
                            event.preventDefault();
                            load_search_results($(this).attr('href'));
                        });
                    }
                );
            };

            // initialise modal when finished loading
            function bind_events_on_modal_content() {
                // hookup events within modal
                $modal.find('form').submit(function(event) {
                    event.preventDefault();
                    load_search_results(
                        $(this).attr('action'),
                        $(this).serialize()
                    );
                });
                // select on first load
                selectable($modal.find(settings.result_child_selector));
                // intercept pagination links
                $modal.find('div.listingBar a').click( function(event) {
                    event.preventDefault();
                    load_search_results($(this).attr('href'));
                });
            };

            // clear modal on close
            $modal.on('hidden', function() {
                $(this).removeData('modal');
                $(this).find('.modal-body').empty();
            });

            // when user preses 'save' button in modal
            $modal.find('button.btn-primary').click(function(event) {
                event.preventDefault();
                // get selected element
                var $selected = $modal.find('.ui-selected');
                // we have all the data we need so get rid of the modal
                $modal.modal('hide');
                if ($selected.length) {
                    // fetch html for widget
                    var params = [];
                    // TODO: this different to original ... maybe adding to current can depend on settings.multiple?
                    // get currently selected datasets
                    var $cursel = $('input[name^="' + settings.widgetname + '"]');
                    $.each($cursel, function(index, dsinput) {
                        params.push({name: settings.widgetname, value:$(dsinput).val()});
                    });
                    // add newly selected datasets
                    var uuid = $selected.map(function() { return $(this).attr('data-uuid'); }).get();
                    $.each(uuid, function(index, value){
                        params.push({name: settings.widgetname, value: value});
                    });
                    $('#' + settings.widgetid + '-selected').load(
                        settings.widgeturl + ' ' + settings.widgetelement,
                        params,
                        function(text, status, xhr) {
                            // trigger change event when widget has been updated
                            $(this).trigger('widgetChanged');
                        }

                    );
                }
            });

            $('#' + settings.widgetid + '-selected')
                .on('click', 'a:has(i.icon-remove)',
                    function(event){
                        event.preventDefault();
                        $(this).parents('div.selecteditem').remove();
                        // trigger change event on widget update
                        $(event.delegateTarget).trigger('widgetChanged');
                    });

            // TODO: this is different to original
            //       there is also a hardcoded reference to another widget this one depends on
            $('#form-widgets-species_distribution_models-selected')
                .on('widgetChanged', function(event, par1, par2) {
                    // update settings with new search parameters
                    var $exp = $(this).find('p.experiment-title');
                    var newparams;
                    if ($exp.length > 0) {
                        newparams = {
                            layers: $exp.data('layers').split(','),
                            resolution: $exp.data('resolution')
                        };
                    }
                    // check if params have changed
                    if ((settings.params === undefined || settings.params === null ||
                         newparams === undefined || newparams === null) ||
                        settings.params.layers.sort().join() != newparams.layers.sort().join() ||
                        settings.params.resolution != newparams.resolution) {
                        // there are either no new settings or new settings are different
                        //let's update this widget here
                        var $elem1 = $('#' + settings.widgetid + '-selected');
                        $elem1.find('div.selecteditem').remove();
                        if (newparams === undefined || newparams === null) {
                            // remove settings.param attribute
                            delete settings.params;
                        } else {
                            // set new params
                            settings.params = newparams;
                        }
                    }

                });
        };


        // single/multi select dataset widget
        // TODO: again a copy of bccvl.select_dataset
        bccvl.select_experiment = function($element, options) {

            // required options: field, genre

            var settings = $.extend({
                // These are the defaults.
                target: '#' + options.field + '-modal',
                remote: 'datasets_listing_popup', // modal box id
                widgetname: 'form.widgets.' + options.field,
                widgetid: 'form-widgets-' + options.field,
                widgeturl: location.origin + location.pathname + '/++widget++' + options.field, // used to reload entire widget
                widgetelement: 'div.selecteditem',
                result_selector: '#datasets-popup-result',
                result_child_selector: '#datasets-popup-result-list',
                filters: ['text', 'source'],
                experimenttype: undefined
            }, options );

            // TODO: this is different to original
            //       there is also a hardcoded reference to another widget this one depends on
            // init settings experimenttype from widget if necessary
            var $experiment_type = $('#form-widgets-experiment_type');
            if (!settings.experimenttype && $experiment_type.val()) {
                settings.experimenttype = [$experiment_type.val()];
            }
            // end diff


            // variable names that make more sense
            var $modal = $(settings.target);
            // move $modal to top level body element to avoid nested form elements
            $modal.prependTo($('body'));

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [{name: 'datasets.multiple',
                                  value: settings.multiple}];
                $.each(settings.filters, function(index, value) {
                    paramlist.push({name: 'datasets.filters:list',
                                    value: value});
                });
                $.each(settings.genre, function(index, value) {
                    paramlist.push({name: 'datasets.filter.genre:list',
                                    value: value});
                });
                $.each(settings.experimenttype, function(index, value){
                    paramlist.push({name: 'datasets.filter.experimenttype:list',
                                    value: value});
                });
                // bootstrap 2 modal does'n have loaded event so we have to do it ourselves
                $modal.modal('show')
                    .find('.modal-body')
                    .load(settings.remote + '?' + $.param(paramlist), function() {
                        bind_events_on_modal_content();
                    });
            });

            function load_search_results(url, params) {
                $modal.find(settings.result_selector).load(
                    url + ' ' + settings.result_child_selector, params,
                    // reapply select events
                    function() {
                        selectable($modal.find(settings.result_child_selector));
                        // intercept pagination links
                        $modal.find('div.listingBar a').click( function(event) {
                            event.preventDefault();
                            load_search_results($(this).attr('href'));
                        });
                    }
                );
            };

            // initialise modal when finished loading
            function bind_events_on_modal_content() {
                // hookup events within modal
                $modal.find('form').submit(function(event) {
                    event.preventDefault();
                    load_search_results(
                        $(this).attr('action'),
                        $(this).serialize()
                    );
                });
                // select on first load
                selectable($modal.find(settings.result_child_selector));
                // intercept pagination links
                $modal.find('div.listingBar a').click( function(event) {
                    event.preventDefault();
                    load_search_results($(this).attr('href'));
                });
            };

            // clear modal on close
            $modal.on('hidden', function() {
                $(this).removeData('modal');
                $(this).find('.modal-body').empty();
            });

            // TODO: modified to accomodate for count field and include already selected datasets
            // when user preses 'save' button in modal
            $modal.find('button.btn-primary').click(function(event) {
                event.preventDefault();

		var $widgetroot = $('div[data-fieldname="' + settings.widgetname + '"]');
		
                // get selected element
                var $selected = $modal.find('.ui-selected');
                var uuid = $selected.map(function() { return $(this).attr('data-uuid'); }).get();
                // we have all the data we need so get rid of the modal
                $modal.modal('hide');
                if ($selected.length) {
		    var $count = $('input[name="' + settings.widgetname + '.count"]');
		    // update count field to add new selection from modal
		    var count = $count.val() || 0;
		    $count.val(count + $selected.length);
		    // collect already selected datasets
		    var params = $widgetroot.find('input,select').serializeArray();
                    // collect newly selected datasets
                    $.each(uuid, function(index, value) {
                        params.push({name: settings.widgetname + '.experiment.' + count,
                                     value: value});
                        count += 1;
                    });
                    // add count parameter if it was not on page already
		    if ($count.length == 0) {
			params.push({name: settings.widgetname + '.count',
                                     value: count});
		    }
                    //fetch html for widget
                    $('#' + settings.widgetid + '-selected').load(
                        settings.widgeturl + ' ' + settings.widgetelement,
                        params,
                        function(text, status, xhr) {
                            // trigger change event when widget has been updated
                            $(this).trigger('widgetChanged');
                        }

                    );
                }
            });

            $('#' + settings.widgetid + '-selected').on('click', 'a:has(i.icon-remove)',
                function(event){
                    event.preventDefault();
                    $(this).parents('div.selecteditem').remove();
                    // trigger change event on widget update
                    $(event.delegateTarget).trigger('widgetChanged');
                }
            );

            // TODO: this is different to original
            //       there is also a hardcoded reference to another widget this one depends on
            $experiment_type
                .on('change', function(event, par1, par2) {
                    // update settings with new search parameters
                    var exptype = $(this).val();
                    // check if params have changed
                    if (exptype != settings.experimenttype) {
                        settings.experimenttype = [exptype];
                        // clear depndent widget
                        var $elem1 = $('#' + settings.widgetid + '-selected');
                        $elem1.find('div.selecteditem').remove();
                    }
                });

        };





    }(jQuery)
);
