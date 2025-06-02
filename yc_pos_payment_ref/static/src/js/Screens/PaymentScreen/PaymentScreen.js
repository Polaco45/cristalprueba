odoo.define('yc_pos_payment_ref.PaymentScreen', function(require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const session = require('web.session');
    const { useListener } = require("@web/core/utils/hooks");

    const PosCashDenominationPaymentScreen = PaymentScreen =>
        class extends PaymentScreen {
            setup() {
                super.setup();
                useListener('add-pay_ref-payment-line', this.openPaymentRef);
            }
            async openPaymentRef(event) {
                var self = this;
                const { cid } = event.detail;
                const line = this.paymentLines.find((line) => line.cid === cid);

                const { confirmed, payload } = await this.showPopup('PaymentDetailPopup', {
                    payment_ref: line.get_payment_ref(),
                    payment_note: line.get_payment_note(),
                });
                if (confirmed) {
                    if (line){
                        line.set_payment_ref(payload['payment_ref']);
                        line.set_payment_note(payload['payment_note']);
                    }
                }
            }
        };

    Registries.Component.extend(PaymentScreen, PosCashDenominationPaymentScreen);

    return PaymentScreen;
});
