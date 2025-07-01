from odoo import models, api, fields
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
from .intent_handlers.onboarding import WhatsAppOnboardingHandler
from .intent_handlers.intent_handlers import handle_solicitar_factura, handle_respuesta_faq
import logging
import json

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    def _add_product_to_cart(self, memory, product_id, quantity, product_name):
        """Agrega un producto al carrito en memoria y retorna el mensaje de confirmación."""
        current_lines = json.loads(memory.order_lines_buffer or '[]')
        
        # Verificar si el producto ya está en el carrito para sumar la cantidad
        found = False
        for line in current_lines:
            if line.get('product_id') == product_id:
                line['quantity'] += quantity
                found = True
                break
        
        if not found:
            current_lines.append({'product_id': product_id, 'quantity': quantity})

        memory.write({
            'order_lines_buffer': json.dumps(current_lines),
            'flow_state': 'esperando_confirmacion_pedido',
            'data_buffer': '',
            'last_variant_id': False,
            'last_qty_suggested': False,
        })
        
        return f"Listo, agregué {quantity} x {product_name} a tu pedido. ¿Querés agregar algo más?"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            def _send_text(to_rec, text_to_send):
                self.env['whatsapp.message'].create({
                    'mobile_number': to_rec.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id,
                })._send_message()

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)
            
            if not partner:
                 # Lógica de onboarding aquí si es necesario
                _logger.info(f"Usuario desconocido {phone}, no se procesa.")
                continue

            memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({'partner_id': partner.id})
            
            memory.write({'timestamp': fields.Datetime.now()})

            if not is_cotizado(partner):
                _send_text(record, "Gracias por escribirnos 😊. Un asesor te va a contactar para cotizarte.")
                continue

            flow = memory.flow_state
            _logger.info(f"💬 Mensaje: '{plain}' | Partner: {partner.name} | Flujo: {flow}")

            # --- MANEJO DE FLUJOS MULTIPASO ---
            if flow == 'esperando_seleccion_producto':
                try:
                    data = json.loads(memory.data_buffer or '{}')
                    variants = data.get('products', [])
                    qty = data.get('qty')
                    
                    if plain.strip().isdigit():
                        index = int(plain.strip()) - 1
                        if 0 <= index < len(variants):
                            selected_variant = variants[index]
                            pid = selected_variant['id']
                            name = selected_variant['name']
                            avail = int(selected_variant['stock'])

                            if not qty:
                                memory.write({'flow_state': 'esperando_cantidad_producto', 'last_variant_id': pid, 'data_buffer': json.dumps({'product': selected_variant})})
                                _send_text(record, f"¡Perfecto! Elegiste “{name}”. ¿Cuántas unidades querés?")
                            elif qty <= avail:
                                response_msg = self._add_product_to_cart(memory, pid, qty, name)
                                _send_text(record, response_msg)
                            else: # No hay stock
                                memory.write({'flow_state': 'esperando_confirmacion_stock', 'last_variant_id': pid, 'last_qty_suggested': avail, 'data_buffer': json.dumps({'original_qty': qty})})
                                _send_text(record, f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar")
                        else:
                            _send_text(record, "Opción no válida. Por favor, respondé con el número del producto que querés.")
                    else:
                        _send_text(record, "Por favor, respondé con el NÚMERO de la opción deseada.")
                except (ValueError, json.JSONDecodeError) as e:
                    _logger.error(f"Error procesando selección: {e}")
                    memory.write({'flow_state': False, 'data_buffer': ''})
                    _send_text(record, "Hubo un error. Empecemos de nuevo. ¿Qué necesitás?")
                continue

            if flow == 'esperando_cantidad_producto':
                try:
                    qty = int(plain.strip())
                    variant = self.env['product.product'].sudo().browse(memory.last_variant_id.id)
                    avail = variant.qty_available or 0
                    if qty <= 0:
                        _send_text(record, "La cantidad debe ser mayor a cero. ¿Cuántas unidades querés?")
                        continue

                    if qty > avail:
                        memory.write({'flow_state': 'esperando_confirmacion_stock', 'last_qty_suggested': avail, 'data_buffer': json.dumps({'original_qty': qty})})
                        _send_text(record, f"Solo hay {avail} unidades de “{variant.display_name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar")
                    else:
                        response_msg = self._add_product_to_cart(memory, variant.id, qty, variant.display_name)
                        _send_text(record, response_msg)
                except ValueError:
                    _send_text(record, "No entendí la cantidad. Por favor, escribí solo el número.")
                continue

            if flow == 'esperando_confirmacion_stock':
                choice = plain.lower().strip()
                var = self.env['product.product'].sudo().browse(memory.last_variant_id.id)
                if choice in ('1', 'sí', 'si'):
                    qty = memory.last_qty_suggested
                    response_msg = self._add_product_to_cart(memory, var.id, qty, var.display_name)
                    _send_text(record, response_msg)
                elif choice in ('2', 'no', 'cancelar'):
                    memory.write({'flow_state': 'esperando_confirmacion_pedido'})
                    _send_text(record, "Entendido, cancelamos este producto. ¿Querés agregar algo más?")
                else:
                    _send_text(record, "No entendí tu respuesta. Por favor, respondé 'Sí' o 'No'.")
                continue
            
            if flow == 'esperando_confirmacion_pedido':
                # El usuario ya tiene productos en el carrito, preguntamos si quiere algo más.
                negative_responses = ['no', 'nono', 'no gracias', 'nada mas', 'eso es todo', 'listo', 'terminar']
                if any(neg in plain.lower() for neg in negative_responses):
                    order_lines = json.loads(memory.order_lines_buffer or '[]')
                    if order_lines:
                        order = create_sale_order(self.env, partner.id, order_lines)
                        summary = "\n".join([f"- {line['quantity']} x {self.env['product.product'].browse(line['product_id']).name}" for line in order_lines])
                        _send_text(record, f"¡Perfecto! 👍\nTu pedido *{order.name}* fue creado con éxito con los siguientes productos:\n{summary}\n\nPronto un asesor se pondrá en contacto con vos. ¡Gracias!")
                        memory.unlink() # Limpia la memoria al finalizar el pedido
                    else:
                        memory.write({'flow_state': False, 'order_lines_buffer': '[]'})
                        _send_text(record, "No hay productos en el pedido. ¿En qué te puedo ayudar?")
                    continue
                # Si no es una negación, se asume que quiere agregar otro producto.
                # El flujo continuará hacia la detección de intención `crear_pedido`.

            # --- DETECCIÓN DE INTENCIÓN ---
            intent = detect_intention([{"role": "user", "content": plain}], self.env['ir.config_parameter'].sudo().get_param('openai.api_key')).lower().strip()
            
            if "crear_pedido" in intent:
                result = handle_crear_pedido(self.env, partner, plain, memory)
                if isinstance(result, str):
                    _send_text(record, result)
                elif isinstance(result, dict): # Producto y cantidad resueltos
                    response_msg = self._add_product_to_cart(memory, result['product_id'], result['quantity'], result['name'])
                    _send_text(record, response_msg)

            elif "solicitar_factura" in intent:
                r = handle_solicitar_factura(partner, plain)
                _send_text(record, r['message'])
            
            elif any(i in intent for i in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]):
                _send_text(record, handle_respuesta_faq(intent, partner, plain))
            
            else: # Fallback
                if flow != 'esperando_confirmacion_pedido': # Solo responder si no estamos en medio de un pedido
                    _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta? Puedo ayudarte a crear pedidos, consultar facturas o responder preguntas frecuentes.")

        return records