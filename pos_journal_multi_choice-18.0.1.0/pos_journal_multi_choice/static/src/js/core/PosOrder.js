/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.invoice_journal_id = vals.invoice_journal_id || false;
        this.custom_journal_id=vals.custom_journal_id || false;

    },
    get_invoice_journal_id() {
        return this.invoice_journal_id;
    },
    get_custom_journal_id() {
        return this.custom_journal_id;
    },
    set_invoice_journal_id(invoice_journal_id) {
        this.custom_journal_id=invoice_journal_id;
        this.invoice_journal_id = invoice_journal_id;
    },

    is_to_journal(journal_id) {
        return this.invoice_journal_id === journal_id;
    },
});
