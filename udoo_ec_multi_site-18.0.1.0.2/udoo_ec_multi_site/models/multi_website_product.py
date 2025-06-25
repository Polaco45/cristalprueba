# -*- coding: utf-8 -*-
# Copyright 2024 Sveltware Solutions

from odoo import fields, models, _


class MultiWebsiteProductReport(models.Model):
    _name = 'multi.website.product.report'
    _description = 'Multi Website Product Report'
    _order = 'website_id, has_websites_set desc'
    _auto = False

    website_id = fields.Many2one('website', 'Website')
    product_id = fields.Many2one('product.template', 'Product')
    product_published = fields.Boolean(
        related='product_id.is_published', string='Global Published', readonly=False
    )
    product_website_url = fields.Char(related='product_id.website_url')
    has_websites_set = fields.Boolean('Has Website Set')
    website_sequence = fields.Integer('Index', aggregator=None)
    is_storable = fields.Boolean('Track Inventory')
    type = fields.Selection(
        [
            ('consu', 'Consumable'),
            ('service', 'Service'),
            ('combo', 'Combo'),
        ],
        string='Product Type',
    )
    invoice_policy = fields.Selection(
        selection=[
            ('order', 'Ordered quantities'),
            ('delivery', 'Delivered quantities'),
        ],
        string='Invoicing Policy',
    )

    @property
    def _table_query(self):
        return """
        WITH onspec AS (
            SELECT 
                website_id
                , product_id
               , TRUE AS has_websites_set
            FROM product_template_public_website_rel
        )
        , nonspec AS (
            SELECT
               web.id AS website_id
               , tmpl.id AS product_id
               , FALSE AS has_websites_set
            FROM website web
            CROSS JOIN product_template tmpl
            WHERE
                tmpl.id NOT IN (SELECT product_id FROM onspec)
        )
        , aggr AS (
            SELECT * FROM onspec
            UNION ALL
            SELECT * FROM nonspec
        )
        SELECT ROW_NUMBER() OVER (ORDER BY product_id) id
            , aggr.website_id
            , aggr.product_id
            , aggr.has_websites_set
            , tmpl.website_sequence
            , tmpl.type
            , tmpl.is_storable
            , tmpl.invoice_policy
        FROM aggr
        JOIN product_template tmpl
            ON tmpl.id = product_id
            AND tmpl.sale_ok
        """

    def action_open_reference(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.product_id.id,
        }

    def action_go_to_website(self):
        self.website_id._force()
        return {
            'type': 'ir.actions.act_url',
            'url': self.product_website_url,
            'target': 'new',
        }
