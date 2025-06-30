from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
from .intent_handlers.onboarding import WhatsAppOnboardingHandler
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura,
    handle_respuesta_faq
)
import logging
import json

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

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
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id if to_rec.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': text_to_send})
                if hasattr(out, '_send_message'):
                    out._send_message()

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)

            # --- GESTIÓN DE MEMORIA CENTRALIZADA ---
            memory_model = self.env['chatbot.whatsapp.memory'].sudo()
            memory = memory_model.search([('partner_id', '=', partner.id)], order='timestamp desc', limit=1)
            if not memory:
                memory = memory_model.create({'partner_id': partner.id})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name if partner else 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}")

            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, memory_model
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado")
                _send_text(record, response_msg)
                continue

            if not is_cotizado(partner):
                _logger.info("🚫 Usuario sin cotización: se envía mensaje de asesoramiento")
                _send_text(record, "Gracias por escribirnos 😊. Un asesor te va a contactar para cotizarte.")
                continue

            flow = memory.flow_state
            _logger.info(f"➡️ Flujo actual: {flow}")

            # --- CEREBRO DEL CHATBOT: MANEJO DE FLUJOS ---
            if flow == 'esperando_seleccion_producto':
                try:
                    data = json.loads(memory.data_buffer or '{}')
                    variants = data.get('products', [])
                    qty = data.get('qty')
                    selected_variant = None

                    if plain.strip().isdigit():
                        index = int(plain.strip()) - 1
                        if 0 <= index < len(variants):
                            selected_variant = variants[index]
                    else:
                        for v in variants:
                            if plain.lower() in v['name'].lower():
                                selected_variant = v
                                break
                    
                    if not selected_variant:
                        _send_text(record, "Opción no válida. Por favor, respondé con el número del producto que querés.")
                        continue
                    
                    pid = selected_variant['id']
                    name = selected_variant['name']
                    avail = int(selected_variant['stock'])

                    # --- INICIO DEL BLOQUE CORREGIDO (INDENTACIÓN) ---
                    if not qty:
                        memory.write({
                            'flow_state': 'esperando_cantidad_producto',
                            'last_variant_id': pid,
                            'data_buffer': '' # Limpiamos el buffer que ya no necesitamos
                        })
                        _send_text(record, f"¡Perfecto! Elegiste “{name}”. ¿Cuántas unidades querés?")
                    elif qty <= avail:
                        order = create_sale_order(self.env, partner.id, pid, qty)
                        memory.unlink()
                        _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{name}.")
                    else:
                        memory.write({
                            'flow_state': 'esperando_confirmacion_stock',
                            'last_variant_id': pid,
                            'last_qty_suggested': avail
                        })
                        _send_text(record, f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar")
                    # --- FIN DEL BLOQUE CORREGIDO ---

                except (ValueError, json.JSONDecodeError) as e:
                    _logger.error(f"Error procesando selección: {e}")
                    _send_text(record, "Hubo un error. Empecemos de nuevo. ¿Qué producto buscás?")
                    memory.unlink()
                continue

            if flow == 'esperando_cantidad_producto':
                try:
                    qty = int(plain.strip())
                    # --- CORRECCIÓN: Usar .id para browse ---
                    variant = self.env['product.product'].sudo().browse(memory.last_variant_id.id)
                    avail = variant.qty_available or 0

                    if qty <= 0:
                        _send_text(record, "La cantidad debe ser un número positivo. ¿Cuántas unidades querés?")
                        continue

                    if qty > avail:
                        memory.write({
                            'flow_state': 'esperando_confirmacion_stock',
                            'last_qty_suggested': avail
                        })
                        _send_text(record, f"Solo hay {avail} unidades de “{variant.display_name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar")
                    else:
                        order = create_sale_order(self.env, partner.id, variant.id, qty)
                        _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}.")
                        memory.unlink()
                except ValueError:
                    _send_text(record, "No entendí la cantidad. Por favor, escribí solo el número.")
                continue

            if flow == 'esperando_confirmacion_stock':
                choice = plain.lower().strip()
                if choice in ('1', 'sí', 'si', 'si, esa cantidad'):
                    # --- CORRECCIÓN: Usar .id para browse ---
                    var = self.env['product.product'].sudo().browse(memory.last_variant_id.id)
                    qty = memory.last_qty_suggested
                    order = create_sale_order(self.env, partner.id, var.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{var.display_name}.")
                elif choice in ('2', 'no', 'cancelar'):
                    memory.unlink()
                    _send_text(record, "Entendido, cancelamos el pedido.")
                else:
                    _send_text(record, "No entendí tu respuesta. Por favor, respondé 'Sí' o 'No'.")
                continue

            # ... (resto del código para INTENCIÓN NLP sin cambios) ...
            
            # --- INTENCIÓN NLP ---
            history = self.env['whatsapp.message'].sudo().search([
                ('mobile_number', '=', record.mobile_number),
                ('id', '<=', record.id),
                ('state', 'in', ['received', 'inbound', 'outgoing', 'sent'])
            ], order='id desc', limit=10)

            conv = []
            if memory and memory.last_intent_detected:
                conv.append({
                    "role": "system",
                    "content": f"Contexto actual: intención anterior '{memory.last_intent_detected}'."
                })

            for msg in reversed(history):
                text = clean_html(msg.body or "").strip()
                if not text or text.lower() in ("ok", "gracias", "dale"):
                    continue
                conv.append({
                    "role": "user" if msg.state in ("received", "inbound") else "assistant",
                    "content": text
                })

            intent = detect_intention(conv, self.env['ir.config_parameter'].sudo().get_param('openai.api_key')).lower().strip()
            
            memory.write({'last_intent_detected': intent})

            if intent == "crear_pedido":
                result = handle_crear_pedido(self.env, partner, plain, memory)
                if result:
                    _send_text(record, result)

            elif intent == "solicitar_factura":
                r = handle_solicitar_factura(partner, plain)
                _send_text(record, r['message'])
                if r.get('pdf_base64') and hasattr(record, 'send_whatsapp_document'):
                    fname = f"{partner.name}_factura_{plain.replace(' ', '_')}.pdf"
                    record.send_whatsapp_document(r['pdf_base64'], fname, mime_type='application/pdf')

            elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
                _send_text(record, handle_respuesta_faq(intent, partner, plain))

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return records
