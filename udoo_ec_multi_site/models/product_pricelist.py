# -*- coding: utf-8 -*-
from odoo import models

class ProductPricelist(models.Model):
    _inherit = [
        'product.pricelist',      # el modelo original de Odoo
        'multi.website.mixin',    # nuestro mixin para website_ids
    ]
    # Con esto el campo website_ids y su lógica compute/inverse
    # ya quedan asociados a product.pricelist.
