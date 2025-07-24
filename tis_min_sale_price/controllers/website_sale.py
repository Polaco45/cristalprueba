# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2024. All rights reserved.

from werkzeug.exceptions import NotFound
from odoo import http, fields
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request


class WebsiteSaleInherit(WebsiteSale):
    """website sale inherit"""

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        """
        Main cart management + abandoned cart revival
        access_token: Abandoned cart SO access token
        revive: Revival method when abandoned cart. Can be 'merge' or 'squash'
        """
        order = request.website.sale_get_order()
        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()

        request.session['website_sale_cart_quantity'] = order.cart_quantity

        values = {}
        if access_token:
            abandoned_order = request.env['sale.order'].sudo().search([('access_token', '=', access_token)], limit=1)
            if not abandoned_order:  # wrong token (or SO has been deleted)
                raise NotFound()
            if abandoned_order.state != 'draft':  # abandoned cart already finished
                values.update({'abandoned_proceed': True})
            elif revive == 'squash' or (revive == 'merge' and not request.session.get(
                    'sale_order_id')):  # restore old cart or merge with unexistant
                request.session['sale_order_id'] = abandoned_order.id
                return request.redirect('/shop/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['sale_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session.get(
                    'sale_order_id'):  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})
        min_sale_price = request.website.min_sale_price
        minimum_sale_price = min_sale_price or 0.0
        tax_info = request.website.tax_type or 'tax_excluded'

        values.update({
            'website_sale_order': order,
            'date': fields.Date.today(),
            'suggested_products': [],
            'minimum_sale_price': float(minimum_sale_price),
            'tax_info': tax_info,
        })
        if order:
            order.order_line.filtered(lambda x: not x.product_id.active).unlink()
            values['suggested_products'] = order._cart_accessories()
            values.update(self._get_express_shop_payment_values(order))

        if post.get('type') == 'popover':
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("website_sale.cart_popover", values, headers={'Cache-Control': 'no-cache'})

        return request.render("website_sale.cart", values)

    # @http.route('/shop/payment', type='http', auth='public', website=True, sitemap=False)
    # def shop_payment(self, **post):
    #     """ Payment step. This page proposes several payment means based on available
    #     payment.provider. State at this point :
    #
    #      - a draft sales order with lines; otherwise, clean context / session and
    #        back to the shop
    #      - no transaction in context / session, or only a draft one, if the customer
    #        did go to a payment provider website but closed the tab without
    #        paying / canceling
    #     """
    #     order = request.website.sale_get_order()
    #     extra_step = request.website.viewref('website_sale.extra_info')
    #     min_sale_price = request.env['ir.config_parameter'].sudo().get_param(
    #         'tis_min_sale_price.min_sale_price')
    #     minimum_sale_price = min_sale_price
    #     tax_info = request.env['ir.config_parameter'].sudo().get_param(
    #         'tis_min_sale_price.tax_type')
    #     if extra_step.active:
    #         if minimum_sale_price:
    #             if tax_info == 'tax_excluded':
    #                 if order and order.amount_untaxed <= float(minimum_sale_price):
    #                     values = {
    #                         'website_sale_order': order,
    #                         'post': post,
    #                         'escape': lambda x: x.replace("'", r"\'"),
    #                         'partner': order.partner_id.id,
    #                         'order': order,
    #                     }
    #                     return request.render("website_sale.extra_info", values)
    #
    #             elif tax_info == 'tax_included':
    #                 if order and order.amount_total <= float(minimum_sale_price):
    #                     values = {
    #                         'website_sale_order': order,
    #                         'post': post,
    #                         'escape': lambda x: x.replace("'", r"\'"),
    #                         'partner': order.partner_id.id,
    #                         'order': order,
    #                     }
    #                     return request.render("website_sale.extra_info", values)
    #
    #     if order and (request.httprequest.method == 'POST' or not order.carrier_id):
    #         # Update order's carrier_id (will be the one of the partner if not defined)
    #         # If a carrier_id is (re)defined, redirect to "/shop/payment" (GET method to avoid infinite loop)
    #         carrier_id = post.get('carrier_id')
    #         keep_carrier = post.get('keep_carrier', False)
    #         if keep_carrier:
    #             keep_carrier = bool(int(keep_carrier))
    #         if carrier_id:
    #             carrier_id = int(carrier_id)
    #         order._check_carrier_quotation(force_carrier_id=carrier_id, keep_carrier=keep_carrier)
    #         if carrier_id:
    #             return request.redirect("/shop/payment")
    #
    #     redirection = self._check_cart(order) or self._check_addresses(order)
    #     if redirection:
    #         return redirection
    #
    #     render_values = self._get_shop_payment_values(order, **post)
    #     render_values['only_services'] = order and order.only_services or False
    #
    #     if render_values['errors']:
    #         render_values.pop('payment_methods_sudo', '')
    #         render_values.pop('tokens_sudo', '')
    #
    #     return request.render("website_sale.payment", render_values)

    @http.route('/shop/payment', type='http', auth='public', website=True, sitemap=False)
    def shop_payment(self, **post):
        """ Payment step. This page proposes several payment means based on available
        payment.provider. State at this point :

         - a draft sales order with lines; otherwise, clean context / session and
           back to the shop
         - no transaction in context / session, or only a draft one, if the customer
           did go to a payment provider website but closed the tab without
           paying / canceling
        """
        order = request.website.sale_get_order()
        extra_step = request.website.viewref('website_sale.extra_info')
        min_sale_price = request.env['ir.config_parameter'].sudo().get_param(
            'tis_min_sale_price.min_sale_price')
        minimum_sale_price = min_sale_price
        tax_info = request.env['ir.config_parameter'].sudo().get_param(
            'tis_min_sale_price.tax_type')

        if extra_step.active:
            if minimum_sale_price:
                if tax_info == 'tax_excluded':
                    if order and order.amount_untaxed <= float(minimum_sale_price):
                        values = {
                            'website_sale_order': order,
                            'post': post,
                            'escape': lambda x: x.replace("'", r"\'"),
                            'partner': order.partner_id.id,
                            'order': order,
                        }
                        return request.render("website_sale.extra_info", values)

                elif tax_info == 'tax_included':
                    if order and order.amount_total <= float(minimum_sale_price):
                        values = {
                            'website_sale_order': order,
                            'post': post,
                            'escape': lambda x: x.replace("'", r"\'"),
                            'partner': order.partner_id.id,
                            'order': order,
                        }
                        return request.render("website_sale.extra_info", values)

        if order and (request.httprequest.method == 'POST' or not order.carrier_id):
            carrier_id = post.get('carrier_id')
            if carrier_id:
                carrier_id = int(carrier_id)
                # ✅ Replaced deprecated method with safe call
                order.delivery_set(carrier_id)
                return request.redirect("/shop/payment")

        redirection = self._check_cart(order) or self._check_addresses(order)
        if redirection:
            return redirection

        render_values = self._get_shop_payment_values(order, **post)
        render_values['only_services'] = order and order.only_services or False

        if render_values['errors']:
            render_values.pop('payment_methods_sudo', '')
            render_values.pop('tokens_sudo', '')

        return request.render("website_sale.payment", render_values)

    @http.route('/shop/sale_price', type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def shop_payment_sale_price(self):
        """Check if the current order meets the minimum sale price.
        This function gets the current website order and checks if the order total
        (tax included or excluded) is above a set minimum sale price. The minimum
        sale price and tax type are stored in system settings."""

        order = request.website.sale_get_order()
        min_sale_price = request.env['ir.config_parameter'].sudo().get_param(
            'tis_min_sale_price.min_sale_price')
        minimum_sale_price = min_sale_price
        tax_info = request.env['ir.config_parameter'].sudo().get_param(
            'tis_min_sale_price.tax_type')
        if minimum_sale_price:
            if tax_info == 'tax_excluded':
                if order and order.amount_untaxed <= float(minimum_sale_price):
                    return False
            elif tax_info == 'tax_included':
                if order and order.amount_total <= float(minimum_sale_price):
                    return False
        return True
