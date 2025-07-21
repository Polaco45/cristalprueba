/** @odoo-module **/
import wSaleUtils from "@website_sale/js/website_sale_utils";

var updateCartNavBar = wSaleUtils.updateCartNavBar;

wSaleUtils.updateCartNavBar = function (data) {
    // Call the original function
    updateCartNavBar(data);

    // Parse order totals
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = data['website_sale.total'] || '';

    var totalTagEl = tempDiv.querySelector('strong.monetary_field.text-end.p-0');
    var amountTotalTag = totalTagEl ? totalTagEl.textContent.replace(/[^\d.-]/g, '') : '0.0';
    var order_total = parseFloat(amountTotalTag);

    var cartTotalSubtotalTd = tempDiv.querySelector('td#cart_total_subtotal');
    var amountUntaxedSpan = cartTotalSubtotalTd?.parentElement?.querySelector('td#cart_total_subtotal + td .oe_currency_value');
    var amount_untaxed_tag = amountUntaxedSpan ? amountUntaxedSpan.textContent.replace(/[^\d.-]/g, '') : '0.0';
    var amount_untaxed = parseFloat(amount_untaxed_tag);

    // Min sale amount
    var myDivText = $('#min_sale_amt').text();
    var min_sale_amount = parseFloat(myDivText);

    // Tax type
    var tax_info = $('#tax_information').text().trim();

    // Helper for alert
    function formatAmount(num) {
        return '$' + num.toFixed(2);
    }

    // Logic based on tax setting
    if (tax_info === 'tax_excluded') {
        if (amount_untaxed >= min_sale_amount) {
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-success float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    You have reached the minimum purchase amount!
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                href="/shop/checkout?express=1">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        } else {
            let remaining = min_sale_amount - amount_untaxed;
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-danger float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    The minimum amount is ${formatAmount(min_sale_amount)} — add ${formatAmount(remaining)} to reach this amount.
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                href="/shop/cart">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        }
    }

    if (tax_info === 'tax_included') {
        if (order_total >= min_sale_amount) {
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-success float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    You have reached the minimum purchase amount!
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                href="/shop/checkout?express=1">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        } else {
            let remaining = min_sale_amount - order_total;
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-danger float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    The minimum amount is ${formatAmount(min_sale_amount)} — add ${formatAmount(remaining)} to reach this amount.
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} #{_form_send_navigation and 'w-100 w-lg-auto ms-lg-auto' or 'w-100'}"
                href="/shop/cart">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        }
    }
};
