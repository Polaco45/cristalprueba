from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order_from_cart
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

            # Estado para cuando el cliente está seleccionando un producto de una lista
            if flow == 'esperando_seleccion_producto':
                try:
                    data = json.loads(memory.data_buffer or '{}')
                    variants = data.get('products', [])
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
                        _send_text(record, "Opción no válida. Por favor, respondé con el número o el nombre del producto que querés.")
                        continue
                    
                    pid = selected_variant['id']
                    name = selected_variant['name']
                    
                    # Actualiza la memoria para pedir la cantidad
                    memory.write({
                        'flow_state': 'esperando_cantidad_producto',
                        'last_variant_id': pid,
                        'data_buffer': json.dumps({'product_name': name, 'product_id': pid}) # Guardamos el nombre y id para referencia
                    })
                    _send_text(record, f"¡Perfecto! Elegiste “{name}”. ¿Cuántas unidades querés?")

                except (ValueError, json.JSONDecodeError) as e:
                    _logger.error(f"Error procesando selección: {e}")
                    _send_text(record, "Hubo un error. Empecemos de nuevo. ¿Qué producto buscás?")
                    # reset on error
                    memory.write({ 'flow_state': False, 'data_buffer': '' })
                continue

            # Estado para cuando el cliente está ingresando la cantidad de un producto
            if flow == 'esperando_cantidad_producto':
                try:
                    qty = int(plain.strip())
                    product_data = json.loads(memory.data_buffer or '{}')
                    product_id = product_data.get('product_id')
                    product_name = product_data.get('product_name')

                    if not product_id:
                        _send_text(record, "No se encontró el producto en memoria. Por favor, intentá de nuevo buscando un producto.")
                        memory.write({ 'flow_state': False, 'data_buffer': '' })
                        continue

                    variant = self.env['product.product'].sudo().browse(product_id)
                    avail = variant.qty_available or 0

                    if qty <= 0:
                        _send_text(record, "La cantidad debe ser un número positivo. ¿Cuántas unidades querés?")
                        continue

                    if qty > avail:
                        memory.write({
                            'flow_state': 'esperando_confirmacion_stock',
                            'last_variant_id': variant.id,
                            'last_qty_suggested': avail,
                        })
                        _send_text(record, f"Solo hay {avail} unidades de “{variant.display_name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar")
                    else:
                        # Add item to cart
                        cart = json.loads(memory.data_buffer or '{}').get('cart', [])
                        cart.append({'product_id': variant.id, 'quantity': qty, 'name': variant.display_name})
                        memory.write({
                            'flow_state': 'pedido_en_progreso', # Nuevo estado para el carrito
                            'data_buffer': json.dumps({'cart': cart}),
                            'last_variant_id': False, # Limpiamos para el próximo ítem
                            'last_qty_suggested': False # Limpiamos
                        })
                        _send_text(record, f"¡Perfecto! Agregamos {qty} unidad(es) de “{variant.display_name}” a tu pedido. ¿Querés algo más?")

                except ValueError:
                    _send_text(record, "No entendí la cantidad. Por favor, escribí solo el número.")
                continue

            # Estado para confirmar la cantidad en caso de stock insuficiente
            if flow == 'esperando_confirmacion_stock':
                choice = plain.lower().strip()
                if choice in ('1', 'sí', 'si', 'si, esa cantidad'):
                    var = self.env['product.product'].sudo().browse(memory.last_variant_id.id)
                    qty = memory.last_qty_suggested
                    
                    # Add item to cart with suggested quantity
                    cart = json.loads(memory.data_buffer or '{}').get('cart', [])
                    cart.append({'product_id': var.id, 'quantity': qty, 'name': var.display_name})
                    memory.write({
                        'flow_state': 'pedido_en_progreso',
                        'data_buffer': json.dumps({'cart': cart}),
                        'last_variant_id': False,
                        'last_qty_suggested': False
                    })
                    _send_text(record, f"Agregamos {qty} unidad(es) de “{var.display_name}” a tu pedido. ¿Querés algo más?")
                elif choice in ('2', 'no', 'cancelar'):
                    # Remove the product from data_buffer if it was stored there during selection
                    # and reset flow to allow new product search
                    memory.write({ 'flow_state': False, 'data_buffer': '', 'last_variant_id': False, 'last_qty_suggested': False })
                    _send_text(record, "Entendido, cancelamos la adición de ese producto. ¿Hay algo más en lo que pueda ayudarte?")
                else:
                    _send_text(record, "No entendí tu respuesta. Por favor, respondé 'Sí' o 'No'.")
                continue

            # Nuevo estado: el cliente está en medio de un pedido, podemos agregar más cosas o finalizar
            if flow == 'pedido_en_progreso':
                # Intentar detectar si el usuario quiere agregar más productos o finalizar
                if "no" in plain.lower() and ("gracias" in plain.lower() or "eso es todo" in plain.lower() or "finalizar" in plain.lower()):
                    cart_items = json.loads(memory.data_buffer or '{}').get('cart', [])
                    if cart_items:
                        order = create_sale_order_from_cart(self.env, partner.id, cart_items)
                        memory.write({'flow_state': False, 'data_buffer': '', 'last_intent_detected': False}) # Limpiamos la memoria
                        _send_text(record, f"¡Excelente! Tu pedido {order.name} ha sido creado con los siguientes artículos:\n" + 
                                            "\n".join([f"- {item['quantity']}x {item['name']}" for item in cart_items]) + 
                                            "\nEn breve un asesor se contactará contigo para coordinar el pago y envío. ¡Gracias por tu compra!")
                    else:
                        _send_text(record, "No hay productos en tu carrito. ¿Hay algo más en lo que pueda ayudarte?")
                        memory.write({'flow_state': False, 'data_buffer': '', 'last_intent_detected': False}) # Limpiamos la memoria
                    continue
                else:
                    # Si no dice "no" o "finalizar", asumimos que quiere seguir agregando productos
                    # Re-evaluar la intención para buscar productos
                    _logger.info("➡️ Cliente en 'pedido_en_progreso' no ha finalizado, re-evaluando intención de agregar producto.")
                    intent = detect_intention(conv, self.env['ir.config_parameter'].sudo().get_param('openai.api_key')).lower().strip()
                    memory.write({'last_intent_detected': intent}) # Actualizar la intención para que handle_crear_pedido la use

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
                    "content": f"Contexto actual: intención anterior '{memory.last_intent_detected}'. El usuario está en el proceso de un pedido si el flow_state es 'pedido_en_progreso'."
                })
            
            # Add previous messages to context, excluding the last one if it's an assistant message
            for msg in reversed(history):
                text = clean_html(msg.body or "").strip()
                if not text or text.lower() in ("ok", "gracias", "dale"):
                    continue
                conv.append({
                    "role": "user" if msg.state in ("received", "inbound") else "assistant",
                    "content": text
                })

            # Check if the last message in history was from the assistant and if so, remove it
            # This helps to avoid the assistant "talking to itself" based on its own previous response
            if conv and conv[-1]['role'] == 'assistant':
                conv.pop()
            
            # Ensure the current user message is always the last in the conversation for NLP
            if conv and (not conv[-1]['role'] == 'user' or conv[-1]['content'] != plain):
                conv.append({"role": "user", "content": plain})
            elif not conv: # If conversation is empty, add the current message
                conv.append({"role": "user", "content": plain})

            _logger.info(f"Conversación enviada al NLP: {conv}")
            intent = detect_intention(conv, self.env['ir.config_parameter'].sudo().get_param('openai.api_key')).lower().strip()
            _logger.info(f"Intención detectada: {intent}")
            
            # Only update last_intent_detected if it's not 'pedido_en_progreso' and the intent is valid
            if memory.flow_state != 'pedido_en_progreso' or (intent != 'crear_pedido' and intent != 'ninguna'):
                memory.write({'last_intent_detected': intent})
            
            if intent == "crear_pedido":
                # Si el flujo es 'pedido_en_progreso', no re-establecemos el flujo, solo agregamos el producto.
                # handle_crear_pedido ahora debe ser capaz de agregar al carrito existente.
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
                # Si el cliente estaba en un flujo de pedido y cambia de tema, mantenemos el carrito.
                # Podríamos agregar una opción para "olvidar el carrito" si cambian mucho de tema.
                # Por ahora, simplemente no limpiamos el flow_state si es un FAQ.

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")
                # Si el cliente estaba en un flujo de pedido y el chatbot no entiende,
                # mantenemos el carrito y el flujo de 'pedido_en_progreso'.
                if memory.flow_state == 'pedido_en_progreso':
                    _send_text(record, "¿Querés agregar algo más o querés finalizar tu pedido?")
                else:
                    memory.write({'flow_state': False, 'data_buffer': ''}) # Reset if no active relevant flow

        return records