/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            // 1) Dejar "Factura" chequeado por defecto al entrar en la pantalla
            const order = this.currentOrder || this.pos.get_order?.();
            if (order && order.to_invoice !== true) {
                order.set_to_invoice(true);
                this.render(); // refrescar UI
            }

            // Mantener tu selección de diario por defecto
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

    // Selección de diarios (no forzar desmarcar factura)
    click_diarios(journal_id) {
        const order = this.currentOrder;
        this.render();

        if (order.get_invoice_journal_id() !== journal_id) {
            order.set_invoice_journal_id(journal_id);
        } else {
            // Antes: quitabas el diario y desmarcabas factura
            // Ahora: solo quitamos el diario seleccionado (si querés)
            order.set_invoice_journal_id(false);
            // NO tocar order.set_to_invoice(false);
        }
    },

    // 2) No cambiar el flag de factura según el método de pago
    addNewPaymentLine(paymentMethod) {
        // Antes: si id !== 9, desmarcabas factura. Eso se elimina.
        return super.addNewPaymentLine(...arguments);
    },
});
