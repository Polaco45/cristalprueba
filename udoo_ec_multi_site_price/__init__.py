# -*- coding: utf-8 -*-
from . import models

def post_init_hook(cr, registry):
    """
    Migra el valor antiguo website_id al nuevo campo Many2many public_website_ids.
    Se ejecuta sólo una vez al instalar/actualizar el módulo.
    """
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    Pricelist = env['product.pricelist']
    for pl in Pricelist.search([]):
        if pl.website_id:
            pl.write({'public_website_ids': [(4, pl.website_id.id)]})
