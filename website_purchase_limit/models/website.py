# -*- coding: utf-8 -*-
from odoo import models, fields


class Website(models.Model):
    _inherit = 'website.website'

    # Nuevo campo: límite mínimo de compra para ESTE sitio
    purchase_limit = fields.Float(
        string="Purchase Limit",
        help="Monto mínimo de compra para este sitio web"
    )

    # Para activar/desactivar el límite en ESTE sitio
    enabled_limit = fields.Boolean(
        string="Enable Purchase Limit",
        help="Habilitar o deshabilitar el límite de compra para este sitio"
    )
