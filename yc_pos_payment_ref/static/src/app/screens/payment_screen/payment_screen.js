/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { useErrorHandlers, useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { DatePickerPopup } from "@point_of_sale/app/utils/date_picker_popup/date_picker_popup";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component, useState, onMounted } from "@odoo/owl";
import { Numpad, enhancedButtons } from "@point_of_sale/app/generic_components/numpad/numpad";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";
import { handleRPCError } from "@point_of_sale/app/errors/error_handlers";
import { sprintf } from "@web/core/utils/strings";
import { serializeDateTime } from "@web/core/l10n/dates";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { PaymentDetailPopup } from "@yc_pos_payment_ref/app/utils/payment_detail_popup/payment_detail_popup";

patch(PaymentScreen.prototype, {
	setup() {
        super.setup();
        this.dialog = useService("dialog");
    },
    async addPaymentRefLine(uuid) {
        const line = this.paymentLines.find((line) => line.uuid === uuid);
        await this.dialog.add(PaymentDetailPopup, {
            payment_ref: line.get_payment_ref(),
            payment_note: line.get_payment_note(),
            getPayload: (payload) => {
                if (payload) {
                    line.set_payment_ref(payload['payment_ref']);
                    line.set_payment_note(payload['payment_note']);
                }
            },
        });
        // const { confirmed, payload } = await this.popup.add(PaymentDetailPopup, {
        //     payment_ref: line.get_payment_ref(),
        //     payment_note: line.get_payment_note(),
        // });
        // if (confirmed) {
        //     if (line){
        //         line.set_payment_ref(payload['payment_ref']);
        //         line.set_payment_note(payload['payment_note']);
        //     }
        // }
    },
});

PaymentScreenPaymentLines.props = {
    ...PaymentScreenPaymentLines.props, 
    addPayRefLine: { type: Function },
}

console.log(">>>>>>>>>>PaymentScreenPaymentLines>>>>>>>", PaymentScreenPaymentLines)