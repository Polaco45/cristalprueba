odoo.define('yc_pos_payment_ref.PaymentDetailPopup', function(require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
    const Registries = require('point_of_sale.Registries');
    const { parse } = require('web.field_utils');
    const { useState } = owl;

    /**
     * Even if this component has a "confirm and cancel"-like buttons, this should not be an AbstractAwaitablePopup.
     * We currently cannot show two popups at the same time, what we do is mount this component with its parent
     * and hide it with some css. The confirm button will just trigger an event to the parent.
     */
    class PaymentDetailPopup extends AbstractAwaitablePopup {
        setup() {
            super.setup();
            this.state = useState({
                payment_ref: '',
                payment_note: '',
            });
            if(this.props.payment_ref != undefined){
                this.state.payment_ref = this.props.payment_ref;
            }
            if(this.props.payment_note != undefined){
                this.state.payment_note = this.props.payment_note;
            }
        }
        paymentRefChanged(ev) {
            this.state.payment_ref = ev.target.value;
        }
        paymentNoteChanged(ev) {
            this.state.payment_note = ev.target.value;
        }
        confirm() {
            return super.confirm();
        }
        getPayload() {
            return {
                payment_ref: String(this.state.payment_ref),
                payment_note: String(this.state.payment_note),
            };
        }
    }

    PaymentDetailPopup.template = 'PaymentDetailPopup';
    PaymentDetailPopup.defaultProps = {
        payment_ref: '',
        payment_note: '',
    };
    Registries.Component.add(PaymentDetailPopup);

    return PaymentDetailPopup;

});
