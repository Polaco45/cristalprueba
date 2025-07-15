# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import ast
from odoo.fields import Command
from collections import defaultdict
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def _ew_is_valid_partner(self, program):
        """
        Check if the customer is eligible for a loyalty program based on partner domains.
        """
        res = False
        domain = []
        if program.ew_rule_partners_domain and program.ew_rule_partners_domain != "[]":

            domain = expression.AND(
                [ast.literal_eval(program.ew_rule_partners_domain), domain]
            )
        domain+=[('id','=',self.partner_id.id)]
        
        if self.env["res.partner"].search_count(domain):
            res =  True
        return res
    
    def _ew_filter_eligible_rewards(self, rewards):
        res = rewards.filtered(
                        lambda reward: (
                            reward.reward_type != 'shipping'
                            or reward.shipping_allowed_type == 'all'
                            or (
                                self.partner_shipping_id.country_id
                                and self.partner_shipping_id.country_id.id in [country.id for country in reward.shipping_allowed_countries]
                            )
                        )
                    )
        return res
    
    def _is_program_used_by_partner(self, program):
        """
        Check if the given loyalty program has been used by a specific customer.

        :param program: Object of the loyalty program to check.
        :return: Boolean, True if the program is already used by the partner, False otherwise.
        """
        partner_id = self.partner_id
        # Ensure valid inputs
        if not program or not partner_id:
            return True

        records = self.env['sale.order.line'].sudo().search_count([
            ('reward_id', 'in', program.reward_ids.ids),
            ('order_id.state', '!=', 'draft'),
            ('order_id.partner_id', '=', partner_id.id)
        ])
        
        # If any records are found, the program has been used
        if records:
            return True
        # # Search for loyalty cards linked to the program_id
        loyalty_cards = self.env['loyalty.card'].sudo().search_count([
            ('program_id', '=', program.id),
            ('order_id', '!=', False),
            ('order_id', '!=', self.id),
            ('order_id.state', '!=', 'draft'),
            ('order_id.partner_id', '=', partner_id.id),
            ('use_count', '>', 0)  # Directly filter cards that have been used
        ])
        
        # If any records are found, the program has been used
        return bool(loyalty_cards)
        
    
    def __try_apply_program(self, program, coupon, status):
        if program:
            # Check if program is invalid or already used
            if not self._ew_is_valid_partner(program) or (program.is_one_use_per_customer and self._is_program_used_by_partner(program)):
                coupons = coupon or self.env['loyalty.card']
                # coupons = self.env['loyalty.card']
                return {'coupon': coupons}
            
        result = super(SaleOrder, self).__try_apply_program(program, coupon, status)
        return result


    def _try_apply_code(self, code):
        res = super()._try_apply_code(code)
        if 'error' in res:
            return res
        base_domain = self._get_trigger_domain()
        domain = expression.AND(
            [base_domain, [("mode", "=", "with_code"), ("code", "=", code)]]
        )
        program = self.env["loyalty.rule"].search(domain).program_id
        
        if not program:
            program = self.env["loyalty.card"].search([("code", "=", code)]).program_id
        # Check that the partner is valid when applying the coupon code.
        if not self._ew_is_valid_partner(program):
            return {"error": _("Not eligible for this reward.")}
        
        if program.is_one_use_per_customer and self._is_program_used_by_partner(program):
            return {"error": _("This reward is limited to one use per customer and has already been used.")}
        
        rewards = self._ew_filter_eligible_rewards(program.reward_ids)
        if not rewards:
            return {"error": _("Not eligible for this reward.")}
        
        return res

    def _get_claimable_rewards(self, forced_coupons=None):
        """
        Filters the claimable rewards based on customer eligibility.
        """
        # Get the original results
        res = super()._get_claimable_rewards(forced_coupons)
        filtered_res = {}
        # Iterate over coupons and check customer eligibility
        for coupon, rewards in res.items():
            # Check if the customer is eligible for the reward
            customer_based_condition = self._ew_is_valid_partner(coupon.program_id)
            if coupon.program_id.is_one_use_per_customer and self._is_program_used_by_partner(coupon.program_id):
                continue
            if customer_based_condition:
                rewards = self._ew_filter_eligible_rewards(rewards)
                # If there are valid rewards, add them to the filtered results
                if rewards:
                    filtered_res[coupon] = rewards
        return filtered_res

    def _get_reward_line_values(self, reward, coupon, **kwargs):
        self.ensure_one()
        if reward.reward_type == 'shipping':
            partner_country = self.partner_shipping_id.country_id
            if partner_country and reward.shipping_allowed_type and reward.shipping_allowed_type != 'all':
                # Check if the partner's country is not in the allowed countries
                if partner_country not in reward.shipping_allowed_countries:
                    request.session['shipping_code_error'] = _(
                        "Free Shipping offer isn't available for your shipping address."
                    )
                    return []
        return super()._get_reward_line_values(reward, coupon, **kwargs)
    
    def get_loyalty_code_error(self, delete=True):
        error = request.session.get('loyalty_code_error')
        if error and delete:
            request.session.pop('loyalty_code_error')
        return error
    
    def get_shipping_code_error(self, delete=True):
        error = request.session.get('shipping_code_error')
        if error and delete:
            request.session.pop('shipping_code_error')
        return error