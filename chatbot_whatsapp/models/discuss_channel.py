# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError
from ..utils.utils import normalize_phone # Asegúrate que esta importación sea correcta
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def _get_customer_partner_and_memory(self):
        """
        Método ayudante para encontrar el partner cliente y su memoria de chatbot.
        Reutiliza la lógica que ya validamos.
        """
        self.ensure_one()
        partner = self.env['res.partner']
        
        # Método 1: Por número de WhatsApp
        if hasattr(self, 'whatsapp_number') and self.whatsapp_number:
            customer_phone = normalize_phone(self.whatsapp_number)
            if customer_phone:
                partner = self.env['res.partner'].sudo().search([
                    '|', ('phone', '=', customer_phone), ('mobile', '=', customer_phone)
                ], limit=1)

        # Método 2: Por miembros del canal (fallback)
        if not partner:
            customer_partners = self.channel_partner_ids.filtered(
                lambda p: not p.user_ids and p.id != self.env.ref('base.partner_root').id
            )
            if len(customer_partners) == 1:
                partner = customer_partners
        
        if not partner:
            raise UserError(_("No se pudo identificar un único cliente en este canal."))

        memory = self.env['chatbot.whatsapp.memory'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        return memory

    def action_pause_chatbot(self):
        """Pausa el chatbot manualmente con una duración larga."""
        for channel in self:
            try:
                memory = channel._get_customer_partner_and_memory()
                if memory:
                    # Pausa manual por 24 horas, reiniciable si se vuelve a pausar.
                    takeover_duration_hours = 24 
                    memory.sudo().write({
                        'human_takeover': True,
                        'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours),
                        'flow_state': False,
                    })
                    _logger.info(f"Chatbot pausado manualmente para el canal {channel.name} por el usuario {self.env.user.name}")
            except UserError as e:
                _logger.warning(e)
        return True # Devuelve True para confirmar la acción al JS

    def action_resume_chatbot(self):
        """Reanuda el chatbot manualmente."""
        for channel in self:
            try:
                memory = channel._get_customer_partner_and_memory()
                if memory:
                    memory.sudo().write({
                        'human_takeover': False,
                        'takeover_until': False,
                    })
                    _logger.info(f"Chatbot reanudado manualmente para el canal {channel.name} por el usuario {self.env.user.name}")
            except UserError as e:
                _logger.warning(e)
        return True # Devuelve True para confirmar la acción al JS

    def get_chatbot_status(self):
        """
        * Método para que el frontend pregunte el estado actual del bot.
        * """
        self.ensure_one()
        try:
            memory = self._get_customer_partner_and_memory()
            if memory and memory.human_takeover:
                return {'status': 'paused'}
        except UserError:
            return {'status': 'unknown'}
        return {'status': 'active'}