/** @odoo-module **/
import wSaleUtils from "@website_sale/js/website_sale_utils";

const updateCartNavBar = wSaleUtils.updateCartNavBar;

// --- Sobrescribimos la función original ---
wSaleUtils.updateCartNavBar = function (data) {
    // 1. Llamamos a la versión original para que Odoo actualice todo
    updateCartNavBar(data);

    /* -------------------- Valores clave -------------------- */
    // Parseamos el HTML que devuelve el servidor
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = data['website_sale.total'] || '';

    // Total con impuestos incluidos
    const totalTagEl = tempDiv.querySelector('strong.monetary_field.text-end.p-0');
    const order_total = parseFloat(
        (totalTagEl?.textContent || '0').replace(/[^\d.-]/g, '')
    );

    // Sub-total sin impuestos
    const amountUntaxedSpan = tempDiv
        .querySelector('td#cart_total_subtotal + td .oe_currency_value');
    const amount_untaxed = parseFloat(
        (amountUntaxedSpan?.textContent || '0').replace(/[^\d.-]/g, '')
    );

    // Mínimo configurado en tu plantilla
    const min_sale_amount = parseFloat($('#min_sale_amt').text() || '0');

    // ¿El negocio está configurado “Impuestos incluidos” o “excluidos”?
    const tax_info = $('#tax_information').text().trim();

    /* -------------------- Limpio mensajes previos -------------------- */
    $('#min_sale_amt_alert').empty();

    /* -------------------- Mensajes y CTA -------------------- */
    // Función auxiliar para pintar el botón de checkout
    const paintCheckoutBtn = (enabled) => {
        const href = enabled ? '/shop/checkout?express=1' : '/shop/cart';
        const classes = 'btn btn-primary w-100 w-lg-auto ms-lg-auto';
        $('a[name="website_sale_main_button"]').replaceWith(
            `<a role="button" name="website_sale_main_button" href="${href}" class="${classes}">
                <span>Checkout</span> <i class="fa fa-angle-right ms-2 fw-light"></i>
            </a>`
        );
    };

    // Comprobamos contra el mínimo según la regla de impuestos
    let cumpleMinimo = false;
    if (tax_info === 'tax_excluded') {
        cumpleMinimo = amount_untaxed >= min_sale_amount;
    } else { // tax_included
        cumpleMinimo = order_total >= min_sale_amount;
    }

    if (cumpleMinimo) {
        // ✅ Éxito
        $('#min_sale_amt_alert').html(`
            <div class="alert alert-success" role="alert">
                ✅ ¡Llegaste al mínimo de compra! Podés finalizar tu pedido.
            </div>
        `);
        paintCheckoutBtn(true);
    } else {
        // ❌ No alcanza
        $('#min_sale_amt_alert').html(`
            <div class="alert alert-danger" role="alert">
                ⚠️ El mínimo de compra es <strong>$${min_sale_amount.toLocaleString('es-AR')}</strong>. 
                Agregá más productos para continuar.
            </div>
        `);
        paintCheckoutBtn(false);
    }
};
