from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class ResPartner(models.Model):
_inherit = 'res.partner'
