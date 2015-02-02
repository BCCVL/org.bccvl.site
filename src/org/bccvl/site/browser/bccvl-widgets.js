
// namespace dictionary to hold all bccvl specific code / widgets
var bccvl = {};

(
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
                result_child_selector: '#datasets-popup-result-list'
            }, options );

            // variable names that make more sense
            var $modal = $(settings.target);

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [];
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
                        params
                    );
                }
            });

        };

        // TODO: differences to widget above:
        //    - the way paramlist is being built (additional datasets.filter.enable_layers parameter)
        //    - parameter list on select  layers button


        bccvl.select_dataset_layers = function($element, options) {

            // required options: field, genre

            var settings = $.extend({
                // These are the defaults.
                target: '#' + options.field + '-modal',
                remote: 'datasets_listing_popup',
                widgetname: 'form.widgets.' + options.field,
                widgetid: 'form-widgets-' + options.field,
                widgeturl: location.origin + location.pathname + '/++widget++' + options.field,
                widgetelement: 'div.selecteditem',
                result_selector: '#datasets-popup-result',
                result_child_selector: '#datasets-popup-result-list'
            }, options );

            // variable names that make more sense
            var $modal = $(settings.target);

            // hookup popup button/link to show modal
            $element.click(function(event) {
                event.preventDefault();
                // show modal
                var paramlist = [{name: 'datasets.filter.enable_layers',
                                  value: 1}];
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
                        params
                    );
                }
            });

        };

    }(jQuery));

$(document).ready( function() {

    // TODO: this shouldn't be global
    $('#form').on('click', 'div.field a:has(i.icon-remove)', function(event){
        event.preventDefault();
        $(this).parents('div.selecteditem').remove();
    });

});
