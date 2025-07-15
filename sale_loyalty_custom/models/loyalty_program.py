from odoo import api, fields, models

class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"
    _description = "Loyalty Program"

    # Char Fields
    ew_rule_partners_domain = fields.Char(
        string="Based on Customers",
        help="Loyalty program will work for selected customers only",
        default="[]",)
    
    is_one_use_per_customer = fields.Boolean(string='Limit to one use per customer')

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for vals in vals_list:
            if not vals.get("ew_rule_partners_domain", False):
                vals["ew_rule_partners_domain"] = "[]"
        return res

    def _is_already_used_by_customer(self):
        """
        Checks if the loyalty program rewards have been used by the current customer.
        """
        # Get the current user's partner
        user_partner = self.env.user.partner_id

        # If no partner is associated with the user, consider the reward unused
        if not user_partner:
            return False

        # Check if there are any used rewards for the current partner in confirmed orders
        has_used_rewards = self.env['sale.order.line'].sudo().search_count([
            ('reward_id', 'in', self.reward_ids.ids),
            ('order_id.state', '!=', 'draft'),
            ('order_id.partner_id', '=', user_partner.id)
        ]) > 0

        return has_used_rewards
        