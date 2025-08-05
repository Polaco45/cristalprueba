/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";
import GraphRenderer from "@affiliate_management/js/graph_renderer";


publicWidget.registry.AffiliateStatistics = GraphRenderer.extend({

    start: function() {
        var self = this;
        self.traffic_graph = self._renderTrafficGraph();
        self.order_graph = self._renderOrderGraph();
        self._updateWeeklyGraphs();
        return this._super.apply(this, arguments);
    },

    _renderTrafficGraph: function() {
        let traffic_canvas = $('canvas#trafficGraph')[0];
        let traffic_context = traffic_canvas.getContext('2d');
        let traffic_config = this._createGraphConfig("Pay Per Click", "PPC Reports", "#225cf0");
        return new Chart(traffic_context, traffic_config);
        
    },

    _renderOrderGraph: function() {
        let order_canvas = $('canvas#orderGraph')[0];
        let order_context = order_canvas.getContext('2d');
        let order_config = this._createGraphConfig("Pay Per Sale", "PPS Reports", "#584854");
        return new Chart(order_context, order_config);
    },

    _updateWeeklyGraphs: function() {
        var self = this;
        return this.orm.call('affiliate.visit', 'get_traffic_daily_stats', [parseInt($('span#aff_website_id').text())])
            .then(function(res){
                self.traffic_graph.data.labels = res.day_label;
                self.order_graph.data.labels = res.day_label;
                self.traffic_graph.data.datasets.forEach((dataset) => {
                    dataset.data = res.count_traffic;
                });
                self.order_graph.data.datasets.forEach((dataset) => {
                    dataset.data = res.count_order;
                });
                self.traffic_graph.update();
                self.order_graph.update();
                $('#pills-monthly-tab').removeClass('btn-primary');
                $('#pills-weekly-tab').addClass('btn-primary');
                return res;
            });
    },

    _updateMonthlyGraphs: function() {
        var self = this;
        return this.orm.call('affiliate.visit', 'get_traffic_monthly_stats', [parseInt($('span#aff_website_id').text())])
            .then(function(res){
                self.traffic_graph.data.labels = res.month_label;
                self.order_graph.data.labels = res.month_label;
                self.traffic_graph.data.datasets.forEach((dataset) => {
                    dataset.data = res.count_traffic;
                });
                self.order_graph.data.datasets.forEach((dataset) => {
                    dataset.data = res.count_order;
                });
                self.traffic_graph.update();
                self.order_graph.update();
                $('#pills-weekly-tab').removeClass('btn-primary');
                $('#pills-monthly-tab').addClass('btn-primary');
                return res;
        });
    },

});
