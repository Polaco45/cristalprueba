odoo.define('yc_pos_payment_ref.models', function(require) {
    'use strict';

    var { Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    const session = require('web.session');

    const PosPaymentRef = (Payment) => class PosPaymentRef extends Payment {
        init_from_JSON(json) {
            super.init_from_JSON(...arguments);

            this.payment_ref = json.payment_ref;
            this.payment_note = json.payment_note;
        }
        export_as_JSON() {
            return _.extend(super.export_as_JSON(...arguments), 
            {
                payment_ref: this.payment_ref,
                payment_note: this.payment_note,
            });
        }
        set_payment_ref(payment_ref) {
            this.payment_ref = payment_ref
        }
        set_payment_note(payment_note) {
            this.payment_note = payment_note
        }
        get_payment_ref(){
            return this.payment_ref;
        }
        get_payment_note(){
            return this.payment_note;
        }

    }
    Registries.Model.extend(Payment, PosPaymentRef);

    return 
});
