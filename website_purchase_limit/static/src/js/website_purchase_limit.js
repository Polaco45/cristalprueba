/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.websiteLimit = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    events: {
        'click a[name="website_sale_main_button"]': '_onCheckoutButtonClick',
    },

    init() {
        this._super(...arguments);
    },

    _onCheckoutButtonClick(event) {
        if (this.$el.find("#website_purchase_limit_value").length) {
            event.preventDefault();
            const limit = parseFloat(this.$el.find("#website_purchase_limit_value").attr("limit"));
            const open_deactivate_modal = true;

            const modalHTML = `
            <div class="modal ${open_deactivate_modal ? 'show d-block' : ''}" id="popup_error_message" tabindex="-1" role="dialog">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5>¡El monto mínimo no fue alcanzado!</h5>
                            <button type="button" class="btn-close" data-dismiss="modal"></button>
                        </div>
                        <form class="modal-body" role="form">
                            <p>Para continuar con la compra, el total debe ser mayor a 
                                <b>$${limit.toLocaleString('es-AR')}</b>.
                            </p>
                            <p style="font-size: 0.85rem; color: #555;">
                                Si querés hacer una compra menor, <strong>contactanos por WhatsApp</strong> y vamos a ayudarte personalmente 😊
                            </p>
                        </form>
                    </div>
                </div>
            </div>
            `;
            $("body").append(modalHTML);
            $("body").find("#popup_error_message").find(".btn-close").on("click", function() {
                $("body").find("#popup_error_message").remove();
            });
        }
    }
});
