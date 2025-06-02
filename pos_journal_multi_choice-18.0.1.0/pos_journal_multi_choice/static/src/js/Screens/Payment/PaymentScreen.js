/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            if (this.is_check_default_journal()) {
                this.apply_default_journal();
            }
        });
    },

    is_check_default_journal() {
        const journal_id = this.pos.config.default_journal_id;
        return !!journal_id;
    },

    apply_default_journal() {
        const journal_id = this.pos.config.default_journal_id;
        if (journal_id) {
            this.currentOrder.set_invoice_journal_id(journal_id.id);
        }
    },

    // Función para manejar el clic de selección de diarios
    click_diarios(journal_id) {
        const order = this.currentOrder;

        this.render();

        if (order.get_invoice_journal_id() !== journal_id) {
            order.set_invoice_journal_id(journal_id);
        } else {
            order.set_invoice_journal_id(false);
            order.set_to_invoice(false);
        }
    },

    // Activar factura si se selecciona el método de pago con ID 9
    addNewPaymentLine(paymentMethod) {
        super.addNewPaymentLine(...arguments);
        const order = this.currentOrder;

        if (paymentMethod && paymentMethod.id === 9) {
            order.set_to_invoice(true);
        } else {
            order.set_to_invoice(false);
        }
    },
});
