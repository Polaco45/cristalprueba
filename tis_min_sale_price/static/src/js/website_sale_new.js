/** @odoo-module **/
import wSaleUtils from "@website_sale/js/website_sale_utils";


    var updateCartNavBar = wSaleUtils.updateCartNavBar;

    // Override the function
    wSaleUtils.updateCartNavBar = function (data) {
        // Call the original function
        updateCartNavBar(data);

        //order total
        // Create a temporary div to parse the HTML content
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = data['website_sale.total'];

        // Get the total amount from the strong element
        var amountTotalTag = tempDiv.querySelector('strong.monetary_field.text-end.p-0').textContent.replace(/[^\d.-]/g, '');
        var order_total = parseFloat(amountTotalTag);
        var cartTotalSubtotalTd = tempDiv.querySelector('td#cart_total_subtotal');
        var amountUntaxedSpan = cartTotalSubtotalTd.parentElement.querySelector('td#cart_total_subtotal + td .oe_currency_value');
        var amount_untaxed_tag = amountUntaxedSpan.textContent.replace(/[^\d.-]/g, '');
        var amount_untaxed = parseFloat(amount_untaxed_tag);
        //min sale amount
        var myDivText = $('#min_sale_amt').text();
        var min_sale_amount = parseFloat(myDivText);

        //tax included or excluded
        var tax_info = $('#tax_information').text().trim();
        var form = $('.s_website_form_no_recaptcha').text()

        if (tax_info == 'tax_excluded'){
            if (amount_untaxed >= min_sale_amount)
            {
                $('#min_sale_amt_alert').html('')
                $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                        class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                        href="/shop/checkout?express=1">
                        <span class="">Checkout</span>
                        <i class="fa fa-angle-right ms-2 fw-light"/>
                    </a>`)
            }
            else{

                $('#min_sale_amt_alert').html(`<a t-if="website_sale_order and website_sale_order.website_order_line"
                       class="alert alert-danger float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                        The minimum order amount is ${min_sale_amount}!
                    </a>`)
                $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                        class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                        href="/shop/cart">
                        <span class="">Checkout</span>
                        <i class="fa fa-angle-right ms-2 fw-light"/>
                    </a>`)
            }
        }
        if (tax_info == 'tax_included'){
            if (order_total >= min_sale_amount)
            {
                $('#min_sale_amt_alert').html('')
                $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} w-100 w-lg-auto ms-lg-auto}"
                href="/shop/checkout?express=1">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`)

            }
            else{
            $('a[name="website_sale_main_button"]').replaceWith(`<a role="button" name="website_sale_main_button"
                class="#{_cta_classes} btn btn-primary #{not website_sale_order._is_cart_ready() and 'disabled'} #{_form_send_navigation and 'w-100 w-lg-auto ms-lg-auto' or 'w-100'}"
                href="/shop/cart">
                <span class="">Checkout</span>
                <i class="fa fa-angle-right ms-2 fw-light"/>
            </a>`)

                $('#min_sale_amt_alert').html(`<a t-if="website_sale_order and website_sale_order.website_order_line"
                           class="alert alert-danger float-end d-none d-xl-inline-block text-decoration-none" role="alert">
                           The minimum order amount is ${min_sale_amount}!
                        </a>`)

                }
        }
    }
