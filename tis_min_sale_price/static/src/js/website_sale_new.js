/** @odoo-module **/
import wSaleUtils from "@website_sale/js/website_sale_utils";
import { _t } from "@web/core/l10n/translation";

var updateCartNavBar = wSaleUtils.updateCartNavBar;

// Helper to correctly parse localized currency strings
function parseCurrency(str) {
    if (!str) return 0.0;
    let cleaned = str.replace(/[^\d.,-]/g, '');

    if (cleaned.indexOf(',') > cleaned.indexOf('.')) {
        cleaned = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
        cleaned = cleaned.replace(/,/g, '');
    }

    return parseFloat(cleaned);
}

// Format number into $xxx.xx
function formatAmount(num) {
    return '$' + num.toFixed(2);
}

wSaleUtils.updateCartNavBar = function (data) {
    // Call the original function
    updateCartNavBar(data);

    // Parse order totals
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = data['website_sale.total'] || '';

    var totalTagEl = tempDiv.querySelector('strong.monetary_field.text-end.p-0');
    var order_total = totalTagEl ? parseCurrency(totalTagEl.textContent) : 0.0;

    var cartTotalSubtotalTd = tempDiv.querySelector('td#cart_total_subtotal');
    var amountUntaxedSpan = cartTotalSubtotalTd?.parentElement?.querySelector('td#cart_total_subtotal + td .oe_currency_value');
    var amount_untaxed = amountUntaxedSpan ? parseCurrency(amountUntaxedSpan.textContent) : 0.0;

    // Min sale amount
    var myDivText = $('#min_sale_amt').text();
    var min_sale_amount = parseFloat(myDivText);

    // Tax type
    var tax_info = $('#tax_information').text().trim();

    // Logic based on tax setting
    if (tax_info === 'tax_excluded') {
        if (amount_untaxed >= min_sale_amount) {
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-success float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    ${_t("You have reached the minimum purchase amount!")}
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="btn btn-primary"
                href="/shop/checkout?express=1">
                <span class="">${_t("Checkout")}</span>
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
                class="btn btn-primary"
                href="/shop/cart">
                <span class="">${_t("Checkout")}</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        }
    }

    if (tax_info === 'tax_included') {
        if (order_total >= min_sale_amount) {
            $('#min_sale_amt_alert').html(`
                <div class="alert alert-success float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                    ${_t("You have reached the minimum purchase amount!")}
                </div>
            `);
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="btn btn-primary"
                href="/shop/checkout?express=1">
                <span class="">${_t("Checkout")}</span>
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
                class="btn btn-primary"
                href="/shop/cart">
                <span class="">${_t("Checkout")}</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`);
        }
    }
};
