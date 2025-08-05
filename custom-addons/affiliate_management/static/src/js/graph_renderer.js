/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";

var GraphRenderer = publicWidget.Widget.extend({
    
    selector: '.aff_stats',

    jsLibs: [
        '/web/static/lib/Chart/Chart.js',
    ],

    events: {
        'click #pills-weekly-tab': '_updateWeeklyGraphs',
        'click #pills-monthly-tab': '_updateMonthlyGraphs',
        
    },

    init: function() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
    },

    start: function () {
        return this._super.apply(this, arguments);
    },


    _createGraphConfig: function(title, label, border_color) {
        return {
            type: 'line',
            responsive: true,
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    fill: false,
                    label: _t(label),
                    borderColor: border_color,
                    tension: 0.2,
                }],
            },

            options: {
                plugins: {
                    legend: {
                        display: true,
                        align: 'end',
                    },
                    filler: {
                        propagate: false,
                    },
                    title: {
                        display: true,
                        text: _t(title),
                        font: {
                                'weight': 'bold',
                                'size': 22
                            },
                        padding: 20,
                        color: border_color,
                    },
                },
                scales: {
                    y: {
                        position: 'left',
                    },
                    x: {
                        grid: {
                            display: false,
                        },
                    },
                },
            },
        };
    },
    
});

export default GraphRenderer;
