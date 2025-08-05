# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

#Odoo Module
from odoo import api, fields, models, _

class WkWizardMessage(models.TransientModel):
	_name = "wk.wizard.message"
	_description = "Model is designed for displaying text-based messages and notifications within the application, typically in a pop-up window or new context, facilitating user interaction and communication"

	# -------------------------------------------------------------------------
    # MODEL FIELDS
    # -------------------------------------------------------------------------
	text = fields.Html(string='Message')


	# -------------------------------------------------------------------------
    # Window Action Method
    # -------------------------------------------------------------------------

	@api.model
	def genrated_message(self,message,name='Message/Summary'):
		res = self.create({'text': message})
		return {
			'name'     : name,
			'type'     : 'ir.actions.act_window',
			'res_model': 'wk.wizard.message',
			'view_mode': 'form',
			'target'   : 'new',
			'res_id'   : res.id,
		}
