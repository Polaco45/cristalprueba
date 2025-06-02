/** @odoo-module */

import { constructFullProductName, random5Chars, uuidv4, qrCodeSrc } from "@point_of_sale/utils";
import { parseFloat as oParseFloat } from "@web/views/fields/parsers";
import {
    formatDate,
    formatDateTime,
    serializeDateTime,
    deserializeDate,
    deserializeDateTime,
} from "@web/core/l10n/dates";
import {
    formatFloat,
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ProductConfiguratorPopup } from "@point_of_sale/app/store/product_configurator_popup/product_configurator_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";
import { omit } from "@web/core/utils/objects";

const { DateTime } = luxon;
import { Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Payment.prototype, {
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);

        this.payment_ref = json.payment_ref;
        this.payment_note = json.payment_note;
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.payment_ref = this.payment_ref;
        json.payment_note = this.payment_note;
        return json
    },
    set_payment_ref(payment_ref) {
        this.payment_ref = payment_ref
    },
    set_payment_note(payment_note) {
        this.payment_note = payment_note
    },
    get_payment_ref(){
        return this.payment_ref;
    },
    get_payment_note(){
        return this.payment_note;
    },
});
