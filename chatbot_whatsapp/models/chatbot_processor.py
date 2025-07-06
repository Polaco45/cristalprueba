import json
import logging
import re
import openai
from odoo.exceptions import UserError
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html
from ..config.config import prompts_config, messages_config, general_config
from .intent_handlers.create_order import (
    create_sale_order, handle_modificar_pedido,
    format_cart_for_display, add_item_to_cart, lookup_product_variants
)
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura, handle_respuesta_faq, handle_saludo,
    handle_agradecimiento_cierre, handle_consulta_producto, 
    _generate_invoice_pdf_response, find_invoice_by_number, offer_recent_invoices
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
        flow = self.memory.flow_state
        _logger.info(f"➡️  Procesando flujo: {flow or 'N/A'}")
        if flow:
            flow_handler = getattr(self, f"_handle_flow_{flow}", None)
            if flow_handler:
                return flow_handler()
        return self._handle_general_intent()

    # --- CORRECCIÓN FINAL Y COMBINADA ---
    def _send_response(self, response_data):
        """
        Envía una respuesta en dos pasos:
        1. La registra en el canal de Odoo para visibilidad interna.
        2. La envía al usuario a través de la API de WhatsApp.
        """
        message = response_data.get('message')
        pdf_base64 = response_data.get('pdf_base64')
        filename = response_data.get('filename', 'adjunto.pdf')

        # --- Tarea 1: Registrar en el canal de Odoo (Chatter) ---
        try:
            # Se busca el canal a través del mensaje de correo asociado al msj de WhatsApp
            mail_message = self.record.mail_message_id
            if mail_message and mail_message.model == 'discuss.channel' and mail_message.res_id:
                channel = self.env['discuss.channel'].sudo().browse(mail_message.res_id)
                
                attachment_id_list = []
                if pdf_base64:
                    # Para postear en el chatter, es más seguro crear el adjunto primero
                    chatter_attachment = self.env['ir.attachment'].sudo().create({
                        'name': filename,
                        'datas': pdf_base64,
                        'res_model': 'discuss.channel',
                        'res_id': channel.id
                    })
                    attachment_id_list.append(chatter_attachment.id)
                
                channel.with_user(self.env.ref('base.user_admin')).message_post(
                    body=message,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    attachment_ids=attachment_id_list
                )
                _logger.info(f"✅ Mensaje registrado en el canal de Odoo '{channel.name}'.")
            else:
                _logger.warning("No se encontró un canal de Odoo para registrar el mensaje. Se procederá solo con el envío a WhatsApp.")
        except Exception as e:
            _logger.error(f"⚠️ No se pudo registrar el mensaje en el canal de Odoo: {e}", exc_info=True)

        # --- Tarea 2: Enviar al usuario por WhatsApp (Usando el método que SÍ enviaba) ---
        try:
            _logger.info(f"🚀 Preparando para enviar a WhatsApp: '{message}'")
            vals = {
                'mobile_number': self.record.mobile_number,
                'body': message,
                'state': 'outgoing',
                'wa_account_id': self.record.wa_account_id.id,
                'create_uid': self.env.ref('base.user_admin').id,
            }
            if pdf_base64:
                # Se vuelve a usar el comando (0,0,{...}) que el método 'create' espera
                vals['attachment_ids'] = [(0, 0, {
                    'name': filename,
                    'datas': pdf_base64,
                    'mimetype': 'application/pdf'
                })]
            
            outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
            
            # El método _send_message() es el que realmente despacha el mensaje
            if hasattr(outgoing_msg, '_send_message'):
                outgoing_msg._send_message()
                
            _logger.info(f"✅ Mensaje '{outgoing_msg.id}' procesado para envío a WhatsApp.")
        except Exception as e:
            _logger.error(f"❌ Error crítico al enviar el mensaje a WhatsApp: {e}", exc_info=True)


    def _send_text(self, text_to_send):
        """Función de ayuda para enviar solo mensajes de texto."""
        return self._send_response({'message': text_to_send})

    # ... (El resto del archivo no necesita cambios y se mantiene igual) ...
    def _add_item_and_decide_next_step(self, pid, qty, name):
        add_item_to_cart(self.memory, pid, qty)
        buffer_data = json.loads(self.memory.data_buffer or '{}')
        pending_products = buffer_data.get('pending_products', [])
        if not pending_products:
            _logger.info("🏁 Cola de productos vacía. Finalizando ciclo de agregación.")
            cart_lines = json.loads(self.memory.pending_order_lines or '[]')
            summary = format_cart_for_display(self.env, cart_lines)
            response = messages_config['confirm_item_added'].format(qty=qty, name=name, summary=summary)
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': ''})
            return self._send_text(response)
        else:
            self._send_text(messages_config['item_added_processing_next'].format(qty=qty, name=name))
            return self._process_next_product_in_queue()

    def _process_next_product_in_queue(self):
        buffer_data = json.loads(self.memory.data_buffer or '{}')
        pending_products = buffer_data.get('pending_products', [])
        if not pending_products:
            _logger.info("🏁 Cola de productos ya estaba vacía. Pasando a confirmación final.")
            self.memory.write({'flow_state': 'esperando_confirmacion_pedido', 'data_buffer': ''})
            return self._send_text("¿Querés agregar algo más?")
        current_product = pending_products.pop(0)
        self.memory.write({'data_buffer': json.dumps({'pending_products': pending_products})})
        query = current_product.get('query')
        qty = current_product.get('quantity')
        _logger.info(f"⚙️ Procesando siguiente en la cola: {query} (Cantidad: {qty})")
        try:
            variants = lookup_product_variants(self.env, self.partner, query, limit=6)
        except UserError as ue:
            _logger.warning(f"⚠️ Error buscando variantes para '{query}': {str(ue)}")
            self._send_text(messages_config['processing_next_item'].format(query=query))
            return self._process_next_product_in_queue()
        if len(variants) > 1:
            buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
            self.memory.write({
                'flow_state': 'esperando_seleccion_producto',
                'data_buffer': json.dumps({'products': variants, 'qty': qty, 'original_queue': pending_products}),
            })
            return self._send_text(messages_config['ask_for_clarification'].format(query=query, buttons=buttons))
        variant = variants[0]
        pid, name, avail = variant['id'], variant['name'], int(variant['stock'])
        if not qty:
            self.memory.write({
                'flow_state': 'esperando_cantidad_producto',
                'last_variant_id': pid,
                'data_buffer': json.dumps({'original_queue': pending_products}),
            })
            return self._send_text(messages_config['ask_for_quantity'].format(name=name))
        if qty <= avail:
            return self._add_item_and_decide_next_step(pid, qty, name)
        else:
            self.memory.write({
                'flow_state': 'esperando_confirmacion_stock',
                'last_variant_id': pid,
                'last_qty_suggested': avail,
                'data_buffer': json.dumps({'original_queue': pending_products}),
            })
            return self._send_text(messages_config['insufficient_stock'].format(avail=avail, name=name))

    def _handle_flow_esperando_confirmacion_pedido(self):
        system_prompt = prompts_config['order_confirmation_system']
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        specialized_intent = detect_intention([{"role": "user", "content": self.plain_text}], api_key, system_prompt)
        
        if specialized_intent == "finalizar_pedido":
            _logger.info("✅ Intención detectada: finalizar_pedido")
            order_lines_data = json.loads(self.memory.pending_order_lines or '[]')
            if not order_lines_data:
                self.memory.write({'flow_state': False, 'pending_order_lines': '[]'})
                return self._send_text(messages_config['cart_is_empty'])

            delivery_addresses = self.partner.child_ids.filtered(lambda c: c.type == 'delivery')
            
            if len(delivery_addresses) > 1:
                _logger.info(f"🚚 Múltiples direcciones de entrega ({len(delivery_addresses)}) encontradas para {self.partner.name}.")
                
                address_lines = []
                for i, addr in enumerate(delivery_addresses):
                    parts = [
                        addr.name,
                        addr.street,
                        addr.city,
                        addr.state_id.name,
                        addr.zip,
                        addr.country_id.name
                    ]
                    formatted_address = ", ".join(filter(None, parts))
                    address_lines.append(f"{i+1}) {formatted_address}")
                
                address_list_str = "\n".join(address_lines)
                
                self.memory.write({
                    'flow_state': 'esperando_seleccion_direccion',
                    'data_buffer': json.dumps({'addresses': delivery_addresses.ids})
                })
                
                final_message = messages_config['ask_for_delivery_address'].format(addresses=address_list_str)
                return self._send_text(final_message)
            else:
                shipping_id = delivery_addresses.id if delivery_addresses else self.partner.id
                order = create_sale_order(self.env, self.partner.id, order_lines_data, partner_shipping_id=shipping_id)
                summary = format_cart_for_display(self.env, order.order_line.mapped(lambda l: {'product_id': l.product_id.id, 'quantity': int(l.product_uom_qty)}))
                response = messages_config['order_finalized'].format(order_name=order.name, summary=summary)
                
                self.memory.write({'flow_state': False, 'data_buffer': '', 'pending_order_lines': '[]'})
                return self._send_text(response)
        
        elif specialized_intent == 'modificar_pedido':
            _logger.info("✅ Intención detectada: modificar_pedido")
            response = handle_modificar_pedido(self.env, self.memory)
            return self._send_text(response)
        
        else:
            _logger.info("✅ Intención detectada: continuar_pedido.")
            self.memory.write({'flow_state': False})
            return self._handle_general_intent()

    def _handle_flow_esperando_seleccion_direccion(self):
        """Maneja la selección de la dirección de entrega por parte del usuario."""
        try:
            data = json.loads(self.memory.data_buffer or '{}')
            address_ids = data.get('addresses', [])
            
            if not (self.plain_text.isdigit() and 1 <= int(self.plain_text) <= len(address_ids)):
                return self._send_text(messages_config['invalid_address_option'])

            selected_address_id = address_ids[int(self.plain_text) - 1]
            _logger.info(f"🚚 Dirección de entrega seleccionada: ID {selected_address_id}")

            order_lines_data = json.loads(self.memory.pending_order_lines or '[]')
            
            order = create_sale_order(self.env, self.partner.id, order_lines_data, partner_shipping_id=selected_address_id)
            
            summary = format_cart_for_display(self.env, order.order_line.mapped(lambda l: {'product_id': l.product_id.id, 'quantity': int(l.product_uom_qty)}))
            response = messages_config['order_finalized'].format(order_name=order.name, summary=summary)
            
            self.memory.write({'flow_state': False, 'data_buffer': '', 'pending_order_lines': '[]'})
            
            return self._send_text(response)
            
        except (ValueError, json.JSONDecodeError, IndexError) as e:
            _logger.error(f"Error en el flujo de selección de dirección: {e}")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['error_processing'])

    def _handle_flow_esperando_seleccion_producto(self):
        """
        Maneja la respuesta del usuario tras mostrar una lista. Puede entender selección
        por nombre, número o contexto, y también preguntas de seguimiento o cancelaciones.
        """
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['product_selection_intent_system']
        sub_intent = detect_intention([{"role": "user", "content": self.plain_text}], api_key, system_prompt)
        
        _logger.info(f"🔎 Sub-intención detectada en selección: '{sub_intent}'")
        data = json.loads(self.memory.data_buffer or '{}')

        if sub_intent == 'seleccionar_producto':
            try:
                variants, qty = data.get('products', []), data.get('qty')
                
                disambiguation_prompt = prompts_config['product_disambiguation_prompt']
                product_names = [v['name'] for v in variants]
                
                resp = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": disambiguation_prompt},
                        {"role": "user", "content": f"Lista: {product_names}\nRespuesta de usuario: \"{self.plain_text}\""}
                    ],
                    temperature=0,
                )
                
                try:
                    selected_index = int(resp.choices[0].message.content.strip())
                except ValueError:
                    selected_index = -1

                if 0 <= selected_index < len(variants):
                    selected_variant = variants[selected_index]
                else:
                    return self._send_text(messages_config['invalid_option'])
                
                self.memory.write({'data_buffer': json.dumps({'pending_products': data.get('original_queue', [])})})
                pid, name, avail = selected_variant['id'], selected_variant['name'], int(selected_variant['stock'])

                if not qty:
                    self.memory.write({
                        'flow_state': 'esperando_cantidad_producto', 'last_variant_id': pid, 
                        'data_buffer': self.memory.data_buffer
                    })
                    return self._send_text(messages_config['ask_for_quantity'].format(name=name))
                
                if qty <= avail:
                    return self._add_item_and_decide_next_step(pid, qty, name)
                else:
                    self.memory.write({
                        'flow_state': 'esperando_confirmacion_stock', 'last_variant_id': pid, 
                        'last_qty_suggested': avail, 'data_buffer': self.memory.data_buffer
                    })
                    return self._send_text(messages_config['insufficient_stock'].format(avail=avail, name=name))

            except (ValueError, json.JSONDecodeError, openai.error.OpenAIError) as e:
                _logger.error(f"Error procesando selección de producto con IA: {e}")
                self.memory.write({'flow_state': False, 'data_buffer': ''})
                return self._send_text(messages_config['error_processing'])

        elif sub_intent == 'nueva_consulta':
            _logger.info("El usuario hizo una nueva consulta sobre los productos mostrados.")
            products_in_context = data.get('products', [])
            context_for_ai = "Productos en contexto:\n" + "\n".join([f"- {p['name']} (${p['price']:.2f})" for p in products_in_context])
            comparison_prompt = prompts_config['product_comparison_prompt']
            try:
                resp = openai.ChatCompletion.create(
                    model=general_config['openai']['model'],
                    messages=[
                        {"role": "system", "content": comparison_prompt},
                        {"role": "user", "content": f"{context_for_ai}\n\nPregunta del cliente: '{self.plain_text}'"}
                    ],
                    temperature=0.7
                )
                return self._send_text(resp.choices[0].message.content)
            except Exception as e:
                _logger.error(f"Error en la sub-consulta de producto: {e}")
                return self._send_text(messages_config['error_processing'])
        
        elif sub_intent == 'cancelar_seleccion':
            _logger.info("El usuario canceló la selección de producto.")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['selection_cancelled'])

        else:
            return self._send_text(messages_config['invalid_option'])


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
                return self._add_item_and_decide_next_step(variant.id, qty, variant.display_name)
        except ValueError:
            return self._send_text(messages_config['invalid_quantity_format'])

    def _handle_flow_esperando_confirmacion_stock(self):
        choice = self.plain_text.lower().strip()
        if choice in ('1', 'sí', 'si', 'si, esa cantidad'):
            var = self.env['product.product'].sudo().browse(self.memory.last_variant_id.id)
            qty = self.memory.last_qty_suggested
            return self._add_item_and_decide_next_step(var.id, qty, var.display_name)
        
        elif choice in ('2', 'no', 'cancelar'):
            self.memory.write({'flow_state': False})
            self._send_text(messages_config['confirm_stock_cancellation'])
            return self._process_next_product_in_queue()
        
        else:
            return self._send_text(messages_config['invalid_stock_confirmation'])
        
    def _handle_flow_esperando_numero_factura(self):
        """Maneja la respuesta del usuario cuando se le pidió un número de factura."""
        _logger.info(f"🧾 El usuario proveyó el texto: '{self.plain_text}' como número de factura.")
        
        if "buscar" in self.plain_text.lower():
             response_data = offer_recent_invoices(self.env, self.partner)
        else:
            response_data = find_invoice_by_number(self.env, self.partner, self.plain_text)
        
        if response_data.get('flow_state'):
            self.memory.write({'flow_state': response_data['flow_state'], 'data_buffer': response_data.get('data_buffer', '')})
        else:
            self.memory.write({'flow_state': False, 'data_buffer': ''})

        return self._send_response(response_data)

    def _handle_flow_esperando_seleccion_factura(self):
        """Maneja la selección de una factura de la lista."""
        if self.plain_text.lower() == 'cancelar':
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['invoice_selection_cancelled'])
        
        try:
            data = json.loads(self.memory.data_buffer or '{}')
            invoice_ids = data.get('invoice_ids', [])
            if not (self.plain_text.isdigit() and 1 <= int(self.plain_text) <= len(invoice_ids)):
                return self._send_text(messages_config['invalid_invoice_option'])

            selected_invoice_id = invoice_ids[int(self.plain_text) - 1]
            invoice = self.env['account.move'].sudo().browse(selected_invoice_id)
            response_data = _generate_invoice_pdf_response(invoice)
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_response(response_data)
        except (ValueError, json.JSONDecodeError, IndexError) as e:
            _logger.error(f"Error en el flujo de selección de factura: {e}")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['error_processing'])     
    
    def _handle_crear_pedido_intent(self):
        """Inicia el proceso de creación de pedido, obteniendo y encolando productos."""
        openai.api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['create_order_system']
        
        try:
            resp = openai.ChatCompletion.create(
                model=general_config['openai']['model'],
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": self.plain_text}],
                functions=prompts_config['create_order_function'],
                function_call={"name": "lookup_product_variants"},
                temperature=0,
            )
            msg = resp.choices[0].message
        except Exception as e:
            _logger.error(f"❌ Error en la llamada a OpenAI: {e}")
            return self._send_text(messages_config['error_processing'])

        if not msg.get('function_call'):
            return self._send_text(messages_config['error_default'])

        args = json.loads(msg.function_call.arguments)
        products_to_add = args.get('products', [])
        if not products_to_add:
            return self._send_text(messages_config['product_not_found_gpt'])

        _logger.info(f"🛒 Productos detectados por IA para encolar: {products_to_add}")
        self.memory.write({
            'flow_state': False,
            'data_buffer': json.dumps({'pending_products': products_to_add})
        })
        
        return self._process_next_product_in_queue()

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
        
        if intent in ["saludo", "agradecimiento_cierre"]:
            handler = {"saludo": handle_saludo, "agradecimiento_cierre": handle_agradecimiento_cierre}[intent]
            response_text = handler(self.env, self.partner, self.plain_text) if intent == "agradecimiento_cierre" else handler(self.env, self.partner)
            return self._send_text(response_text)

        if intent in ["crear_pedido", "modificar_pedido"]:
            if intent == "crear_pedido": return self._handle_crear_pedido_intent()
            if intent == "modificar_pedido": return self._send_text(handle_modificar_pedido(self.env, self.memory))

        if intent in ["consulta_producto", "solicitar_factura"]:
            handler = {"consulta_producto": handle_consulta_producto, "solicitar_factura": handle_solicitar_factura}[intent]
            response_data = handler(self.env, self.partner, self.plain_text)
            
            if response_data.get('flow_state'):
                self.memory.write({'flow_state': response_data['flow_state'], 'data_buffer': response_data.get('data_buffer', '')})
            
            return self._send_response(response_data)

        faq_response = handle_respuesta_faq(self.partner, self.plain_text)
        if faq_response:
            return self._send_text(faq_response)
        return self._send_text(messages_config['error_default'])
    
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