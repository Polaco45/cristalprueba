/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { floatIsZero } from "@web/core/utils/numbers";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { NumericInput } from "@point_of_sale/app/generic_components/inputs/numeric_input/numeric_input";
import { Dialog } from "@web/core/dialog/dialog";

export class PaymentDetailPopup extends Component {
    static template = "yc_pos_payment_ref.PaymentDetailPopup";
    static components = { Dialog };
    static props = {
        payment_ref: { type: String, optional: true },
        payment_note: { type: String, optional: true },
        close: { type: Function, optional: true },
        getPayload:{ type: Function, optional: true },
    };
    static defaultProps = {
        payment_ref: '',
        payment_note: '',
        description: '',
    };
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
        this.props.getPayload({
            payment_ref: String(this.state.payment_ref),
            payment_note: String(this.state.payment_note),
        });
        this.props.close();
    }
    cancel() {
        this.props.close();
    }
}