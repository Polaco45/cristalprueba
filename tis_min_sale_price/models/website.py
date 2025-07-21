# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd. - ©
# Technaureus Info Solutions Pvt. Ltd 2024. All rights reserved.
from odoo import models, fields, _
from odoo.tools.translate import _lt
from odoo.http import request


class Website(models.Model):
    """Inherits the 'website' model to customize the checkout process with per-website sale conditions."""
    _inherit = 'website'

    min_sale_price = fields.Float(string='Minimum Sale Price')
    tax_type = fields.Selection([
        ('tax_included', 'Tax Included'),
        ('tax_excluded', 'Tax Excluded')],
        string="Tax Type",
        default='tax_excluded')

    def _get_checkout_steps(self, current_step=None):
        """Determine the steps of the checkout process based on various conditions."""
        self.ensure_one()

        is_extra_step_active = self.viewref('website_sale.extra_info').active
        redirect_to_sign_in = self.account_on_checkout == 'mandatory' and self.is_public_user()

        #Use per-website settings
        minimum_sale_price = self.min_sale_price or 0.0
        tax_info = self.tax_type or 'tax_excluded'
        order = request.website.sale_get_order()

        cart_url = f'{"/web/login?redirect=" if redirect_to_sign_in else ""}/shop/checkout?express=1'

        #Apply minimum sale price logic based on tax type
        if minimum_sale_price:
            if tax_info == 'tax_excluded':
                if order and order.amount_untaxed <= minimum_sale_price:
                    cart_url = '/shop/cart'
            elif tax_info == 'tax_included':
                if order and order.amount_total <= minimum_sale_price:
                    cart_url = '/shop/cart'

        steps = [(['website_sale.cart'], {
            'name': _lt("Review Order"),
            'current_href': '/shop/cart',
            'main_button': _lt("Sign In") if redirect_to_sign_in else _lt("Checkout"),
            'main_button_href': cart_url,
            'back_button': _lt("Continue shopping"),
            'back_button_href': '/shop',
        }), (['website_sale.checkout', 'website_sale.address'], {
            'name': _lt("Shipping"),
            'current_href': '/shop/checkout',
            'main_button': _lt("Confirm"),
            'main_button_href': '/shop/extra_info' if is_extra_step_active else '/shop/confirm_order',
            'back_button': _lt("Back to cart"),
            'back_button_href': '/shop/cart',
        })]

        if is_extra_step_active:
            steps.append((['website_sale.extra_info'], {
                'name': _lt("Extra Info"),
                'current_href': '/shop/extra_info',
                'main_button': _lt("Continue checkout"),
                'main_button_href': '/shop/confirm_order',
                'back_button': _lt("Return to shipping"),
                'back_button_href': '/shop/checkout',
            }))

        steps.append((['website_sale.payment'], {
            'name': _lt("Payment"),
            'current_href': '/shop/payment',
            'back_button': _lt("Back to cart"),
            'back_button_href': '/shop/cart',
        }))

        if current_step:
            return next(step for step in steps if current_step in step[0])[1]
        else:
            return steps
