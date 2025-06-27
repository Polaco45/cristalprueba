odoo.define('payment_delivery_discount_web.discount', function (require) {
    "use strict";
    const publicWidget = require('web.public.widget');

    publicWidget.registry.PaymentDeliveryDiscount = publicWidget.Widget.extend({
        selector: '.o_payment, .o_delivery',
        events: {
            'change select': '_onChange',
        },
        _onChange: function () {
            location.reload();
        },
    });
});
