import json
import logging
from odoo.exceptions import UserError
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html
from ..config.config import prompts_config, messages_config
from .intent_handlers.create_order import (
    handle_crear_pedido, create_sale_order, handle_modificar_pedido,
    format_cart_for_display, add_item_to_cart
)
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura, handle_respuesta_faq
)

_logger = logging.getLogger(__name__)

class ChatbotProcessor:
    def __init__(self, env, record, partner, memory):
        self.env = env
        self.record = record
        self.partner = partner
        self.memory = memory
        self.plain_text = clean_html(record.body or "").strip()

    def process_message(self):
        """Punto de entrada principal para procesar un mensaje."""
        flow = self.memory.flow_state
        _logger.info(f"➡️ Procesando flujo: {flow or 'N/A'}")

        if flow:
            flow_handler = getattr(self, f"_handle_flow_{flow}", None)
            if flow_handler:
                return flow_handler()

        if self._is_order_in_progress():
            return self._handle_order_in_progress_intent()
            
        return self._handle_general_intent()

    def _is_order_in_progress(self):
        """Verifica si hay un pedido en curso que no esté en un sub-flujo específico."""
        cart_items = json.loads(self.memory.pending_order_lines or '[]')
        return bool(cart_items and not self.memory.flow_state)

    def _send_text(self, text_to_send):
        """
        Wrapper para enviar mensajes de texto usando el método estándar de Odoo.
        """
        _logger.info(f"🚀 Intentando enviar mensaje: '{text_to_send}'")
        if self.record.wa_account_id:
            # Usamos el método oficial de Odoo para mayor fiabilidad
            self.record.wa_account_id.send_message(self.partner, text_to_send)
            _logger.info("✅ Mensaje pasado al método send_message de Odoo.")
        else:
            _logger.warning("No se pudo enviar el mensaje porque no se encontró una cuenta de WhatsApp (wa_account_id).")

    # --- MANEJADORES DE FLUJOS ESPECÍFICOS ---

    def _handle_flow_esperando_seleccion_eliminar(self):
        cart_lines = json.loads(self.memory.pending_order_lines or '[]')
        if self.plain_text.lower() == 'cancelar':
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido'})
            return self._send_text(messages_config['cancel_modification'])
        
        try:
            index_to_remove = int(self.plain_text)
            if not (1 <= index_to_remove <= len(cart_lines)):
                return self._send_text(messages_config['invalid_number_for_deletion'])
            
            cart_lines.pop(index_to_remove - 1)
            self.memory.write({'pending_order_lines': json.dumps(cart_lines)})
            
            new_summary = format_cart_for_display(self.env, cart_lines)
            response = messages_config['item_removed_confirm'].format(summary=new_summary)
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido'})
            return self._send_text(response)
        except ValueError:
            return self._send_text(messages_config['invalid_input_for_deletion'])

    def _handle_flow_esperando_seleccion_producto(self):
        try:
            data = json.loads(self.memory.data_buffer or '{}')
            variants, qty = data.get('products', []), data.get('qty')
            
            selected_variant = None
            if self.plain_text.isdigit():
                index = int(self.plain_text) - 1
                if 0 <= index < len(variants):
                    selected_variant = variants[index]
            else:
                for v in variants:
                    if self.plain_text.lower() in v['name'].lower():
                        selected_variant = v
                        break

            if not selected_variant:
                return self._send_text(messages_config['invalid_option'])

            pid, name, avail = selected_variant['id'], selected_variant['name'], int(selected_variant['stock'])

            if not qty:
                self.memory.write({'flow_state': 'esperando_cantidad_producto', 'last_variant_id': pid, 'data_buffer': ''})
                return self._send_text(messages_config['ask_for_quantity'].format(name=name))
            
            if qty <= avail:
                add_item_to_cart(self.memory, pid, qty)
                self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': '', 'last_variant_id': False})
                return self._send_text(messages_config['confirm_item_added'].format(qty=qty, name=name))
            else:
                self.memory.write({'flow_state': 'esperando_confirmacion_stock', 'last_variant_id': pid, 'last_qty_suggested': avail})
                return self._send_text(messages_config['insufficient_stock'].format(avail=avail, name=name))
        except (ValueError, json.JSONDecodeError) as e:
            _logger.error(f"Error en flujo de selección: {e}")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['error_processing'])

    def _handle_flow_esperando_cantidad_producto(self):
        try:
            qty = int(self.plain_text)
            if qty <= 0:
                return self._send_text(messages_config['invalid_quantity'])

            variant = self.env['product.product'].sudo().browse(self.memory.last_variant_id.id)
            avail = variant.qty_available or 0

            if qty > avail:
                self.memory.write({'flow_state': 'esperando_confirmacion_stock', 'last_qty_suggested': int(avail)})
                return self._send_text(messages_config['insufficient_stock'].format(avail=int(avail), name=variant.display_name))
            else:
                add_item_to_cart(self.memory, variant.id, qty)
                self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': '', 'last_variant_id': False})
                return self._send_text(messages_config['confirm_item_added'].format(qty=qty, name=variant.display_name))
        except ValueError:
            return self._send_text(messages_config['invalid_quantity_format'])

    def _handle_flow_esperando_confirmacion_stock(self):
        choice = self.plain_text.lower().strip()
        if choice in ('1', 'sí', 'si', 'si, esa cantidad'):
            var = self.env['product.product'].sudo().browse(self.memory.last_variant_id.id)
            qty = self.memory.last_qty_suggested
            
            add_item_to_cart(self.memory, var.id, qty)
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': '', 'last_variant_id': False, 'last_qty_suggested': False})
            return self._send_text(messages_config['confirm_item_added'].format(qty=qty, name=var.display_name))
        
        elif choice in ('2', 'no', 'cancelar'):
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': ''})
            return self._send_text(messages_config['confirm_stock_cancellation'])
        
        else:
            return self._send_text(messages_config['invalid_stock_confirmation'])

    # --- MANEJADORES DE INTENCIONES ---

    def _handle_order_in_progress_intent(self):
        """Maneja las intenciones cuando ya hay un pedido en curso."""
        system_prompt = prompts_config['order_confirmation_system']
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        
        specialized_intent = detect_intention([{"role": "user", "content": self.plain_text}], api_key, system_prompt)
        
        if specialized_intent == "finalizar_pedido":
            order_lines_data = json.loads(self.memory.pending_order_lines or '[]')
            if not order_lines_data:
                self.memory.write({'flow_state': False, 'pending_order_lines': '[]'})
                return self._send_text(messages_config['cart_is_empty'])

            order = create_sale_order(self.env, self.partner.id, order_lines_data)
            summary = "\n".join([f"  - {int(line.product_uom_qty)} × {line.name.splitlines()[0]}" for line in order.order_line])
            response = messages_config['order_finalized'].format(order_name=order.name, summary=summary)
            
            self.memory.write({'flow_state': False, 'data_buffer': '', 'last_variant_id': False, 'last_qty_suggested': False, 'pending_order_lines': '[]'})
            return self._send_text(response)
        
        elif specialized_intent == 'modificar_pedido':
            response = handle_modificar_pedido(self.env, self.memory)
            return self._send_text(response)
        
        else: # Asume 'continuar_pedido'
            return self._handle_general_intent()

    def _handle_general_intent(self):
        """Detecta y despacha la intención general del usuario."""
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['general_intent_system']
        
        history = self.env['whatsapp.message'].sudo().search([
            ('mobile_number', '=', self.record.mobile_number), ('id', '<=', self.record.id),
            ('state', 'in', ['received', 'inbound', 'outgoing', 'sent'])
        ], order='id desc', limit=10)
        
        conv = [{"role": "user" if msg.state in ("received", "inbound") else "assistant", "content": clean_html(msg.body or "").strip()} for msg in reversed(history)]
        
        intent = detect_intention(conv, api_key, system_prompt)
        self.memory.write({'last_intent_detected': intent})
        
        intent_handlers = {
            "crear_pedido": lambda: handle_crear_pedido(self.env, self.partner, self.plain_text, self.memory),
            "modificar_pedido": lambda: handle_modificar_pedido(self.env, self.memory),
            "solicitar_factura": lambda: handle_solicitar_factura(self.partner, self.plain_text).get('message'),
            "consulta_horario": lambda: handle_respuesta_faq(intent, self.partner, self.plain_text),
            "saludo": lambda: handle_respuesta_faq(intent, self.partner, self.plain_text),
            "consulta_producto": lambda: handle_respuesta_faq(intent, self.partner, self.plain_text),
            "ubicacion": lambda: handle_respuesta_faq(intent, self.partner, self.plain_text),
            "agradecimiento": lambda: handle_respuesta_faq(intent, self.partner, self.plain_text),
        }
        
        handler = intent_handlers.get(intent)
        if handler:
            response_message = handler()
            if response_message:
                return self._send_text(response_message)
        else:
            return self._send_text(messages_config['error_default'])