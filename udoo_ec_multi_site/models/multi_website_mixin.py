# -*- coding: utf-8 -*-
from odoo import api, fields, models

class MultiWebsiteMixin(models.AbstractModel):
    _name = 'multi.website.mixin'
    _description = 'Mixin para asignar registros a múltiples Websites'

    public_website_ids = fields.Many2many(
        comodel_name='website',
        relation='multi_website_rel',   # tabla intermedia genérica
        column1='res_id',               # id del registro (template, pricelist…)
        column2='website_id',           # id del website
        string='Websites',
    )
