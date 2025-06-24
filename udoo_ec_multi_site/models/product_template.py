# -*- coding: utf-8 -*-
# Copyright 2024 Sveltware Solutions

from odoo import api, fields, models, _
from odoo.http import request
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    public_website_ids = fields.Many2many(
        string='Websites',
        comodel_name='website',
        relation='product_template_public_website_rel',
        column1='product_id',
        column2='website_id',
    )

    @api.model
    def _search_get_detail(self, website, order, options):
        """
        - If "public_website_ids" is set, only the specified websites can search the product.

        Ref#1: odoo/addons/website/models/mixins.py
            Trace line: 294 -> 320
        Ref#2: odoo/addons/website_sale/models/product_template.py
            Trace line: 20 -> 714 -> 719 -> 772
        """
        res = super()._search_get_detail(website, order, options)
        res['base_domain'].append(
            [
                '|',
                ('public_website_ids', '=', False),
                ('public_website_ids', 'in', website.ids),
            ]
        )
        return res

    @api.depends('is_published', 'website_id', 'public_website_ids')
    @api.depends_context('website_id')
    def _compute_website_published(self):
        """
        Ref#1: odoo/addons/website/models/mixins.py
            Trace line: 238 -> 249 -> 259
        Ref#2: odoo/addons/website_sale/models/product_template.py
            Trace line: 19 -> 188
        Ref#3: odoo/addons/website_sale/models/sale_order.py
            Trace line: 365 -> 370
        Ref#4: odoo/addons/website_sale/security/website_sale.xml
            Trace line: 7
        """
        current_website_id = self._context.get('website_id')
        for record in self.sudo():
            if current_website_id:
                restricts = record.public_website_ids | record.website_id
                record.website_published = record.is_published and (
                    not restricts or current_website_id in restricts.ids
                )
            else:
                record.website_published = record.is_published

    def can_access_from_current_website(self, website_id=False):
        """
        If `public_website_ids` or `website_id` is set. only the specified websites can access the product.
        otherwise, the product is public for all avaiable website.

        Ref#1: odoo/addons/website/models/mixins.py
            Trace line: 158 -> 173 -> 239
        Ref#2: odoo/addons/website_sale/models/product_template.py
            Trace line: 19
        """
        can_access = True
        for product in self:
            restricts = product.public_website_ids | product.website_id
            if restricts:
                current_website_id = request.env['website'].get_current_website().id
                return not (current_website_id not in restricts.ids)
        return can_access

    def open_update_available_website(self):
        if any(not o.sale_ok for o in self):
            raise ValidationError(_("The selected products has not been set to 'Can be Sold'"))

        return {
            'name': _('Update Available Websites'),
            'res_model': 'multi.website.setter',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'set_product': True,
                'default_product_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
