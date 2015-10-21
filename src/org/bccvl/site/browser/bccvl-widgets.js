(

    // TODO: there may be a problem here with various element ids. These widgets may produce/rely on
    //       duplicate id's in the dom.
    function($) {

        // helper function for selectable behaviour
        function Selectable(elements, multi) {
            if (multi) {
                this.multi = true;
            } else {
                this.multi = false;
            }
            
            this.$elements = $(elements);
            this.$elements.click(function(event) {
                // get parent row div
                var $row = $(event.target).closest('.selectable');
                // new state for input element
                if ($row.hasClass('ui-selected') ) {
                    this.unselect($row);
                } else {
                    this.select($row);
                }
            }.bind(this));
        };

        Selectable.prototype.select = function($element) {
            $element.addClass('ui-selected');
            $element.trigger('selected');
            // if not multi select remove all other selections
            if (! this.multi) {
                $.each($element.siblings('.ui-selected'), function(idx, element) {
                    this.unselect($(element));
                }.bind(this));
            }
        };

        Selectable.prototype.unselect = function($element) {
            $element.removeClass('ui-selected');
            $element.trigger('unselected');
        };

        function Basket() {
            this.uuids = [];
        };

        Basket.prototype.add = function(uuid) {
            var idx = $.inArray(uuid, this.uuids);
            if (idx < 0) {
                this.uuids.push(uuid);
            }
        };

        Basket.prototype.remove = function(uuid) {
            var idx = $.inArray(uuid, this.uuids);
            if (idx >= 0) {
                this.uuids.splice(idx, 1);
            }
        };

        Basket.prototype.contains = function(uuid) {
            var idx = $.inArray(uuid, this.uuids);
            return idx >= 0;
        };

        Basket.prototype.elements = function(uuid) {
            return this.uuids;
        };

        Basket.prototype.clear = function() {
            this.uuids = [];
        };

        function ModalBrowseSelect(modalid, options, selected) {

            // FIXME: this becomes a pure id ... no selector?
            this.$modal = $(modalid);
            
            this.settings = $.extend({
                remote: undefined,
                multiple: undefined
            }, options);

            // make sure the modal dialog is a top level element on the page
            this.$modal.prependTo($('body'));
            // init modal events
            this.$modal.on('hidden', this._clear.bind(this) );
            // apply button
            this.$modal.find('button.btn-primary').click(function(event) {
                event.preventDefault();
                // trigger custom event
                this.$modal.trigger('modalapply');
            }.bind(this));

            // TODO: maybe hook up basket directly with selectable object?
            this.basket = new Basket();
        }

        ModalBrowseSelect.prototype.show = function(selected) {
            // show dialog
            // bootstrap 2 modal does'n have loaded event so we have to do it ourselves
            this.$modal.modal('show');
            // init basket in case we have some pre selected elements
            this.basket.clear();
            if (selected) {
                $.each(selected, function(idx, value) {
                    // FIXME: this may circumvent settings.multiple
                    //        for now it's the callers responsibility
                    this.basket.add(value);
                }.bind(this));
            }
            this._init_faceted();
        };


        ModalBrowseSelect.prototype.close = function() {
            this.$modal.modal('hide');
        };

        // hide and clear modal
        ModalBrowseSelect.prototype._clear = function() {
            this.$modal.removeData('modal');
            this.$modal.find('.modal-body').empty();
            Faceted.Cleanup();            
        };

        // load search interface into modal
        ModalBrowseSelect.prototype._init_faceted = function() {
            var self = this;
            this.$modal.find('.modal-body').load(this.settings.remote + '/@@facetednavigation_simple_view', function(event) {
                // apply selectable behaviour
                var selectable = new Selectable($(this).find('#faceted-results'), self.settings.multiple);
                // hookup selectable events with basket
                selectable.$elements.on('selected', function(event) {
                    var uuid = $(event.target).attr('data-uuid');
                    if (! self.settings.multiple) {
                        self.basket.clear();
                    }
                    self.basket.add(uuid);
                });
                selectable.$elements.on('unselected', function(event) {
                    var uuid = $(event.target).attr('data-uuid');
                    self.basket.remove(uuid);
                });
                // init faceted ui
                Faceted.Load(0, self.settings.remote + '/');
                $(Faceted.Events).bind(Faceted.Events.AJAX_QUERY_SUCCESS, function(){
                    // update selection state from basket
                    $.each($("#faceted-results .selectable"), function(idx, element) {
                        var uuid = $(element).attr('data-uuid');
                        if (self.basket.contains(uuid)) {
                            selectable.select($(element));
                        };
                    });
                });
            });
        };

        ModalBrowseSelect.prototype.get_selected = function() {
            return this.basket.elements();
        };

        // TODO: 
        //       set initial filter? (pre-set from current page)
        //       what about pre-set filters from page? -> we set resolution and layer list for future selection
        //       SelectFuture also has special handling to update when another widget changes -> move widget init code out of template and onto page javascript
        //       SelectExperiment -> depends on value from another widget as well (init and change)

        function SelectList(fieldname) {

            this.$widget = $("#form-widgets-" + fieldname);
            
            this.settings = {
                fieldname: fieldname,
                multiple: this.$widget.attr('data-multiple'),
                widgetid: "form-widgets-" + fieldname, // id of widget main top element
                widgetname: "form.widgets." + fieldname, // name of the input field
                widgeturl: location.origin + location.pathname + "/++widget++" + fieldname, // used to reload entire widget
                // modal settings
                modalid: "#" + fieldname + "-modal"
            };
            this.$modaltrigger = $("a#" + fieldname + "-popup");
            
            // init modal
            this.modal = new ModalBrowseSelect(
                this.settings.modalid,
                {
                    remote: this.$modaltrigger.attr('href'),
                    multiple: this.settings.multiple
                }
            );
            
            // hook up events
            // open modal
            this.$modaltrigger.click(this.modal_open.bind(this));
            // apply changes
            this.modal.$modal.on('modalapply', this.modal_apply.bind(this));

            // allow user to remove selected elements
            $('#' + this.settings.widgetid).on('click', 'a:has(i.icon-remove)',
                function(event) {
                    event.preventDefault();
                    $(this).parents('div.selecteditem').remove();
                    // trigger change event on widget update
                    $(event.delegateTarget).trigger('widgetChanged');
                    // TODO: shall we reload the widget?
                }
            );
        };

        SelectList.prototype.reload_widget = function(params) {
            this.$widget.load(
                this.settings.widgeturl + ' #' + this.settings.widgetid + ' >',
                params,
                function(text, status, xhr) {
                    // trigger change event on widget update                        
                    $(this).trigger('widgetChanged');
                }
            );
        };

        SelectList.prototype.modal_open = function(event) {
            event.preventDefault();
            // get currently selected uuids
            uuids = [];
            $.each(this.$widget.find('input.item'), function(idx, element) {
                uuids.push($(element).val());
            });
            // show modal
            this.modal.show(uuids);
        };

        SelectList.prototype.modal_apply = function(event) {
            // get selected element
            var selected = this.modal.get_selected();
            // we have all the data we need so get rid of the modal
            this.modal.close();
            // build params
            var params = [];
            $.each(selected, function(idx, uuid) {
                var $existing = $('input[value="' + uuid + '"]').closest('.selecteditem');
                if ($existing.length > 0) {
                    // we have a previously selected item, let's grab all form elements for it
                    var data = $existing.find('input,select').serializeArray();
                    $.merge(params, data);
                    
                } else {
                    // we have got a new item
                    params.push({name: this.settings.widgetname + ':list',
                                 value: uuid});
                }
            }.bind(this));
            this.reload_widget(params);
        };


        // multi layer select widget        
        function SelectDict(fieldname) {
            SelectList.call(this, fieldname);
        }
        // SelectDict inherits from SelectList
        SelectDict.prototype = Object.create(SelectList.prototype); // inherit prototype        
        SelectDict.prototype.constructor = SelectDict; // use new constructor
        // override modal_apply 
        SelectDict.prototype.modal_apply = function(event) {
            // get selected element
            var selected = this.modal.get_selected();
            // we have all the data we need so get rid of the modal
            this.modal.close();
            // build params
            var count = $('[name="' + this.settings.widgetname + '.count"]').val();
            var params = [];
            $.each(selected, function(idx, uuid) {
                var $existing = $('input[value="' + uuid + '"]').closest('.selecteditem');
                if ($existing.length > 0) {
                    // we have a previously selected item, let's grab all form elements for it
                    var data = $existing.find('input,select').serializeArray();
                    $.merge(params, data);
                    
                } else {
                    // we have got a new item
                    params.push({name: this.settings.widgetname + '.item.' + count,
                                 value: uuid});
                    count += 1;
                }                
            }.bind(this));
            params.push({name: this.settings.widgetname + '.count',
                         value: count});
            this.reload_widget(params);
        };


        // list modal apply
            // when user preses 'save' button in modal
            // TODO: move to prototype as it needs to be overridden
            // modal.$modal.on('modalapply', function(event) {
            //     var $widgetroot = $('#' + settings.widgetid);
            //     // get selected element
            //     var $selected = modal.get_selected();
            //     // we have all the data we need so get rid of the modal
            //     modal.close();
            //     if ($selected.length) {
            //         var params = [];
            //         if (settings.multiple) {
            //             // if multiple fetch current selection
            //             params = $widgetroot.find('input,select').serializeArray();
            //         }
            //         $.each($selected, function(index, value){
            //             params.push({name: settings.widgetname + ':list',
            //                          value: $(value).attr('data-uuid')});
            //         });
            //         reload_widget(params);
            //     }
            // });

        // dict modal apply
            // when user preses 'save' button in modal
            // modal.$modal.on('modalapply', function(event) {
            //     var $widgetroot = $('#' + settings.widgetid);                
            //     // get selected element
            //     var $selected = modal.get_selected();
            //     // we have all the data we need so get rid of the modal
            //     modal.close();
            //     if ($selected.length) {
            //         // first update .count field on widget
            //         var $count = $('input[name="' + settings.widgetname + '.count"]');
            //         var count = parseInt($count.val()) || 0;
            //         $count.val(count + $selected.length);
            //         // get current params from widget
            //         var params = $widgetroot.find('input,select').serializeArray();
            //         // collect newly selected layers
            //         $.each($selected, function(index, value){
            //             params.push({name: settings.widgetname + '.item.' + count,
            //                          value: $(value).attr('data-uuid')});
            //             count += 1;
            //         });
            //         // add count parameter if it was not on page already
            //         if ($count.length == 0) {
            //             params.push({name: settings.widgetname + '.count',
            //                          value: count});
            //         }
            //         // fetch html for widget
            //         reload_widget(params);
            //     }
            // });

        // future modal apply
            // when user preses 'save' button in modal
            // modal.$element.on('modalapply', function(event) {
            //     var $widgetroot = $('#' + settings.widgetid);
            //     // get selected element
            //     var $selected = modal.get_selected();
            //     // we have all the data we need so get rid of the modal
            //     modal.close();
            //     if ($selected.length) {
            //         // get current params for widget
            //         var params = $widgetroot.find('input,select').serializeArray();                    
            //         // TODO: this different to original ... maybe adding to current can depend on settings.multiple?
            //         // add newly selected datasets
            //         $.each($selected, function(index, value){
            //             params.push({name: settings.widgetname + ':list',
            //                          value: $(value).attr('data-uuid')});
            //         });
            //         reload_widget(params);
            //     }
            // });



        // experiment modal apply
            // when user preses 'save' button in modal
            // modal.$element.on('modalapply', function(event) {
            //     var $widgetroot = $('#' + settings.widgetid);
            //     // get selected element
            //     var $selected = modal.get_selected();
            //     // we have all the data we need so get rid of the modal
            //     modal.close();
            //     if ($selected.length) {
            //         var $count = $('input[name="' + settings.widgetname + '.count"]');
            //         // update count field to add new selection from modal
            //         var count = parseInt($count.val()) || 0;
            //         $count.val(count + $selected.length);
            //         // collect already selected datasets
            //         var params = $widgetroot.find('input,select').serializeArray();
            //         // collect newly selected datasets
            //         $.each($selected, function(index, value) {
            //             params.push({name: settings.widgetname + '.experiment.' + count,
            //                          value: $(value).attr('data-uuid')});
            //             count += 1;
            //         });
            //         // add count parameter if it was not on page already
            //         if ($count.length == 0) {
            //             params.push({name: settings.widgetname + '.count',
            //                          value: count});
            //         }
            //         //fetch html for widget
            //         reload_widget(params);
            //     }
            // });


        if (typeof bccvl === 'undefined') {
            bccvl = {};
        }
        $.extend(bccvl, {
            SelectList: SelectList,
            SelectDict: SelectDict
        });


    }(jQuery)



);

jQuery(document).ready( function() {
    new bccvl.SelectList("species_occurrence_dataset");
    new bccvl.SelectList("species_absence_dataset");
    new bccvl.SelectDict("environmental_datasets");
    new bccvl.SelectDict("species_distribution_models");
    new bccvl.SelectList("future_climate_datasets");
    var projection = new bccvl.SelectDict("projection");
    var datasets = new bccvl.SelectDict("datasets");
    new bccvl.SelectList("data_table");
    // TODO: make sure to keep current subitems selected when reloading widget

    // Biodiverse uses selectize 
    $.each(projection.$widget.find('select'), function(index, elem) {
        $(elem).selectize({create: true,
                           persist: false});
    });
    // re init selectize boxes on widget reload
    projection.$widget.on('widgetChanged', function(event) {
        $.each(projection.$widget.find('select'), function(index, elem) {
            $(elem).selectize({create: true,
                               persist: false});
        });
    });


    // Let Ensemble use facet variants based on experiment type select box
    var $experiment_type = $('#form-widgets-experiment_type');
    datasets.modal.settings.remote = datasets.$modaltrigger.attr("href") + '_' + $experiment_type.val();

    $experiment_type
        .on('change', function(event, par1, par2) {
            // update settings with new search parameters
            var exptype = $(this).val();

            datasets.modal.settings.remote = datasets.$modaltrigger.attr("href") + '_' + exptype;
            
            // clear dependent widget
            
            datasets.$widget.empty();
        });
    

});
