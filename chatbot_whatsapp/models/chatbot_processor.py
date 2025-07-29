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
    find_invoice_by_number
)

_logger = logging.getLogger(__name__)

class ChatbotProcessor:
    def __init__(self, env, record, partner, memory):
        self.env = env
        self.record = record
        self.partner = partner
        self.memory = memory
        self.plain_text = clean_html(record.body or "").strip()

    def _is_b2c(self):
        """Verifica si el partner es un cliente B2C (Consumidor Final)."""
        b2c_tag_name = "Tipo de Cliente / Consumidor Final"
        return self.partner.category_id and any(tag.name == b2c_tag_name for tag in self.partner.category_id)

    def process_message(self):
        """
        Procesa el mensaje entrante, priorizando el flujo B2C si el cliente
        está etiquetado como tal.
        """
        flow = self.memory.flow_state
        _logger.info(f"➡️  Procesando flujo: {flow or 'N/A'} para {self.partner.name}")

        if self._is_b2c() and not flow:
            _logger.info("Cliente detectado como B2C. Iniciando manejador B2C.")
            return self._handle_b2c_intent()

        if flow:
            flow_handler = getattr(self, f"_handle_flow_{flow}", None)
            if flow_handler:
                return flow_handler()

        return self._handle_general_intent()

    def _handle_b2c_intent(self):
        """Maneja las intenciones específicas para clientes B2C con respuestas de IA."""
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        openai.api_key = api_key
        system_prompt = prompts_config['general_intent_system']
        history = self.env['whatsapp.message'].sudo().search([
            ('mobile_number', '=', self.record.mobile_number), ('id', '<=', self.record.id),
            ('state', 'in', ['received', 'inbound', 'outgoing', 'sent'])
        ], order='id desc', limit=3)
        conv = [{"role": "user" if msg.state in ("received", "inbound") else "assistant", "content": clean_html(msg.body or "").strip()} for msg in reversed(history)]
        intent = detect_intention(conv, api_key, system_prompt)
        self.memory.write({'last_intent_detected': intent})

        _logger.info(f"👤 Intent B2C detectado: {intent} para {self.partner.name}")

        website_urls = {
            "Tipo de Cliente / Consumidor Final": "https://www.quimicacristal.com.ar",
            "Tipo de Cliente / EMPRESA": "https://www.cristalempresas.com.ar",
            "Tipo de Cliente / Mayorista": "https://www.cristalmayorista.com.ar"
        }
        partner_category_name = self.partner.category_id[0].name if self.partner.category_id else None
        web_url = website_urls.get(partner_category_name, "https://www.quimicacristal.com.ar")

        if intent == "consulta_producto":
            try:
                extraction_prompt = prompts_config['product_extraction_system_prompt']
                resp_ext = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role": "system", "content": extraction_prompt}, {"role": "user", "content": self.plain_text}], temperature=0)
                query = resp_ext.choices[0].message.content.strip()

                try:
                    variants = lookup_product_variants(self.env, self.partner, query)
                except UserError as e:
                    return self._send_text(str(e) + f"\n\nDe todas formas, podés ver todo nuestro catálogo en {web_url} 😉")

                product_list_str = "\n".join([f"- {v['name']} - ${v['price']:.2f}" for v in variants])
                
                system_prompt_b2c = prompts_config['b2c_product_query_prompt']
                user_prompt_b2c = f"Productos encontrados:\n{product_list_str}\n\nURL de la tienda: {web_url}"

                resp_final = openai.ChatCompletion.create(
                    model=general_config['openai']['model'],
                    messages=[
                        {"role": "system", "content": system_prompt_b2c},
                        {"role": "user", "content": user_prompt_b2c}
                    ],
                    temperature=0.7
                )
                return self._send_text(resp_final.choices[0].message.content.strip())
            except Exception as e:
                _logger.error(f"❌ Error en consulta B2C con IA: {e}")
                return self._send_text(messages_config['error_processing'])

        if intent == "crear_pedido":
            try:
                system_prompt_b2c = prompts_config['b2c_create_order_prompt']
                user_prompt_b2c = f"Mensaje del cliente: \"{self.plain_text}\"\nURL de la tienda: {web_url}"

                resp = openai.ChatCompletion.create(
                    model=general_config['openai']['model'],
                    messages=[
                        {"role": "system", "content": system_prompt_b2c},
                        {"role": "user", "content": user_prompt_b2c}
                    ],
                    temperature=0.7
                )
                return self._send_text(resp.choices[0].message.content.strip())
            except Exception as e:
                _logger.error(f"❌ Error en crear_pedido B2C con IA: {e}")
                return self._send_text(messages_config['error_processing'])

        if intent == "solicitar_factura":
            return self._send_text(messages_config['b2c_invoice_response'])

        if intent == "saludo":
            return self._send_text(handle_saludo(self.env, self.partner))

        if intent == "agradecimiento_cierre":
            return self._send_text(handle_agradecimiento_cierre(self.env, self.partner, self.plain_text))

        if intent in ["consulta_horario_direccion", "consulta_informativa", "otro", ""]:
            _logger.info(f"B2C Fallback/Info: Intención '{intent}' detectada. Enviando a handle_respuesta_faq.")
            faq_response = handle_respuesta_faq(self.env, self.partner, self.plain_text, conv)
            return self._send_text(faq_response)

        return self._send_text(messages_config['error_default'])
    
    def _send_template(self, template_name_to_send, partner, invoice):
        """
        Envía una plantilla de WhatsApp para una factura con el número dinámico,
        armando el body manualmente según cómo lo envía el UI.
        """
        wa_account = self.record.wa_account_id
        if not wa_account:
            _logger.error("No se encontró una cuenta de WhatsApp activa.")
            return

        try:
            # Buscar plantilla
            wa_template = self.env['whatsapp.template'].sudo().search([
                ('template_name', '=', template_name_to_send),
                ('wa_account_id', '=', wa_account.id)
            ], limit=1)

            if not wa_template:
                _logger.error(f"No se encontró la plantilla: {template_name_to_send}")
                return

            invoice_number = invoice.name
            
            mail_message = self.env['mail.message'].sudo().create({
            'model': 'account.move',  # Especifica el TIPO de documento
            'res_id': invoice.id,      # Especifica QUÉ documento es
            'body': wa_template.body,
            })

            vals = {
                'mobile_number': partner.phone or partner.mobile,
                'wa_account_id': wa_account.id,
                'wa_template_id': wa_template.id,
                'mail_message_id': mail_message.id,
                'state': 'outgoing',
            }

            outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
            outgoing_msg._send_message()
            _logger.info(f"✅ Plantilla {outgoing_msg.id} enviada para la factura {invoice.name}.")

        except Exception as e:
            _logger.error(f"❌ Error al enviar plantilla: {e}", exc_info=True)

    def _send_response(self, response_data):
        message = response_data.get('message')
        if not message:
            return
        try:
            mail_message = self.record.mail_message_id
            if mail_message and mail_message.model == 'discuss.channel' and mail_message.res_id:
                channel = self.env['discuss.channel'].sudo().browse(mail_message.res_id)
                channel.with_context(from_wa_bot=True).message_post(
                    body=message,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )
        except Exception as e:
            _logger.error(f"⚠️ No se pudo registrar el mensaje de texto en el canal de Odoo: {e}", exc_info=True)
        try:
            vals = {
                'mobile_number': self.record.mobile_number,
                'body': message,
                'state': 'outgoing',
                'wa_account_id': self.record.wa_account_id.id,
                'create_uid': self.env.ref('base.user_admin').id,
            }
            outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
            outgoing_msg.sudo().write({'body': message})
            if hasattr(outgoing_msg, '_send_message'):
                outgoing_msg._send_message()
        except Exception as e:
            _logger.error(f"❌ Error al enviar el mensaje de texto por WhatsApp: {e}", exc_info=True)

    def _send_text(self, text_to_send):
        return self._send_response({'message': text_to_send})
    
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
            variants = lookup_product_variants(self.env, self.partner, query)
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
        data = json.loads(self.memory.data_buffer or '{}')
        variants = data.get('products', [])
        selected_index = -1

        # --- CORRECCIÓN: Manejo directo de selección numérica ---
        if self.plain_text.isdigit():
            try:
                choice = int(self.plain_text)
                if 1 <= choice <= len(variants):
                    selected_index = choice - 1
                    _logger.info(f"✅ Selección numérica directa detectada: índice {selected_index}")
            except (ValueError, IndexError):
                pass

        if selected_index == -1:
            _logger.info("La selección no fue numérica, usando IA para interpretar.")
            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            system_prompt = prompts_config['product_selection_intent_system']
            sub_intent = detect_intention([{"role": "user", "content": self.plain_text}], api_key, system_prompt)
            
            _logger.info(f"🔎 Sub-intención detectada en selección: '{sub_intent}'")

            if sub_intent == 'seleccionar_producto':
                disambiguation_prompt = prompts_config['product_disambiguation_prompt']
                product_names = [v['name'] for v in variants]
                
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": disambiguation_prompt},
                            {"role": "user", "content": f"Lista: {product_names}\nRespuesta de usuario: \"{self.plain_text}\""}
                        ],
                        temperature=0,
                    )
                    selected_index = int(resp.choices[0].message.content.strip())
                except (ValueError, openai.error.OpenAIError) as e:
                    _logger.error(f"Error procesando desambiguación con IA: {e}")
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

        if 0 <= selected_index < len(variants):
            selected_variant = variants[selected_index]
            qty = data.get('qty')
            
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

        # --- LÓGICA MODIFICADA ---
        if not products_to_add:
            _logger.info("🛒 Intención 'crear_pedido' sin productos. Pidiendo al usuario que especifique con IA.")
            try:
                # Se usa el nuevo prompt para generar una pregunta dinámica
                ask_prompt = prompts_config['ask_for_products_prompt']
                
                resp_ask = openai.ChatCompletion.create(
                    model=general_config['openai']['model'],
                    messages=[{"role": "system", "content": ask_prompt}],
                    temperature=0.7 # Un poco de creatividad para variar la respuesta
                )
                ai_response = resp_ask.choices[0].message.content.strip()
                return self._send_text(ai_response)
                
            except Exception as e:
                _logger.error(f"❌ Error generando la pregunta por productos con IA: {e}")
                # Si falla la IA, se usa el mensaje predefinido como respaldo
                return self._send_text(messages_config['product_not_found_gpt'])

        # --- El flujo original continúa si SÍ se encontraron productos ---
        _logger.info(f"🛒 Productos detectados por IA para encolar: {products_to_add}")
        self.memory.write({
            'flow_state': False,
            'data_buffer': json.dumps({'pending_products': products_to_add})
        })
        
        return self._process_next_product_in_queue()
    
    def _handle_flow_esperando_seleccion_o_numero_factura(self):
        """
        Maneja la respuesta del usuario, que puede ser la selección de una factura
        de la lista (ej: '1') o un número de factura completo para buscar.
        """
        if self.plain_text.lower() == 'cancelar':
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['invoice_selection_cancelled'])

        template_name = "envio_factura_chatbot_copy_copy"
        
        # Intenta interpretar la entrada como una selección de la lista (ej: "1", "2", etc.)
        if self.plain_text.isdigit():
            try:
                data = json.loads(self.memory.data_buffer or '{}')
                invoice_ids = data.get('invoice_ids', [])
                choice = int(self.plain_text)
                
                if 1 <= choice <= len(invoice_ids):
                    selected_invoice_id = invoice_ids[choice - 1]
                    invoice = self.env['account.move'].sudo().browse(selected_invoice_id)
                    _logger.info(f"🧾 Usuario seleccionó factura de la lista: {invoice.name}")
                    self.memory.write({'flow_state': False, 'data_buffer': ''})
                    return self._send_template(template_name, self.partner, invoice)
            except (ValueError, json.JSONDecodeError, IndexError):
                # Si falla, no es una selección válida. Lo tratará como un número de factura.
                _logger.warning(f"⚠️ No se pudo procesar '{self.plain_text}' como selección. Intentando como búsqueda.")
                pass

        # Si no fue una selección de la lista, lo trata como un número de factura para buscar
        _logger.info(f"🧾 Buscando factura por número ingresado: '{self.plain_text}'")
        invoice = find_invoice_by_number(self.env, self.partner, self.plain_text)
        
        if invoice:
            _logger.info(f"🧾 Factura encontrada por número: {invoice.name}")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_template(template_name, self.partner, invoice)
        else:
            # Si no se encuentra, se le vuelve a ofrecer la lista.
            _logger.warning(f"🧾 No se encontró factura con '{self.plain_text}'. Re-ofreciendo lista.")
            data = json.loads(self.memory.data_buffer or '{}')
            invoices_in_memory = self.env['account.move'].sudo().browse(data.get('invoice_ids', []))
            
            invoice_lines = [f"{i+1}) *{inv.name}* del {inv.invoice_date.strftime('%d/%m/%Y')} - ${inv.amount_total:,.2f}" for i, inv in enumerate(invoices_in_memory)]
            invoice_list_str = "\n".join(invoice_lines)

            message = messages_config['invoice_search_failed_reoffer'].format(
                number=self.plain_text,
                invoices=invoice_list_str
            )
            return self._send_text(message)
        
    def _handle_flow_esperando_numero_factura(self):
        """
        Maneja el caso donde no había facturas recientes y el usuario
        ingresa un número de factura para una búsqueda directa.
        """
        if self.plain_text.lower() == 'cancelar':
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['invoice_selection_cancelled'])

        template_name = "envio_factura_chatbot_copy_copy"
        invoice = find_invoice_by_number(self.env, self.partner, self.plain_text)

        if invoice:
            _logger.info(f"🧾 Factura encontrada por número: {invoice.name}")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_template(template_name, self.partner, invoice)
        else:
            # Si no se encuentra, se informa al usuario y se resetea el flujo.
            _logger.warning(f"🧾 No se encontró factura con el número '{self.plain_text}'.")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            message = messages_config['invoice_not_found_and_reset'].format(number=self.plain_text)
            return self._send_text(message)
            
    def _handle_general_intent(self):
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['general_intent_system']
        history = self.env['whatsapp.message'].sudo().search([('mobile_number', '=', self.record.mobile_number), ('id', '<=', self.record.id), ('state', 'in', ['received', 'inbound', 'outgoing', 'sent'])], order='id desc', limit=3)
        conv = [{"role": "user" if msg.state in ("received", "inbound") else "assistant", "content": clean_html(msg.body or "").strip()} for msg in reversed(history)]
        intent = detect_intention(conv, api_key, system_prompt)
        self.memory.write({'last_intent_detected': intent})
        _logger.info(f"👤 Intent General detectado: {intent} para {self.partner.name}")

        if intent == "solicitar_factura":
            number_match = re.search(r'[\d\-\s]+', self.plain_text)
            if number_match:
                invoice = find_invoice_by_number(self.env, self.partner, number_match.group())
                if invoice:
                    self.memory.write({'flow_state': False, 'data_buffer': ''})
                    return self._send_template("envio_factura_chatbot_copy_copy", self.partner, invoice)
            response_data = handle_solicitar_factura(self.env, self.partner, self.plain_text)
            if response_data.get('flow_state'):
                self.memory.write({'flow_state': response_data.get('flow_state'), 'data_buffer': json.dumps(response_data.get('data_buffer', {}))})
            return self._send_response(response_data)

        if intent in ["saludo", "agradecimiento_cierre"]:
            handler = {"saludo": handle_saludo, "agradecimiento_cierre": handle_agradecimiento_cierre}[intent]
            response_text = handler(self.env, self.partner, self.plain_text) if intent == "agradecimiento_cierre" else handler(self.env, self.partner)
            return self._send_text(response_text)

        if intent in ["crear_pedido", "modificar_pedido"]:
            if intent == "crear_pedido": return self._handle_crear_pedido_intent()
            if intent == "modificar_pedido": return self._send_text(handle_modificar_pedido(self.env, self.memory))

        if intent == "consulta_producto":
            response_data = handle_consulta_producto(self.env, self.partner, self.plain_text)
            if response_data.get('flow_state'):
                self.memory.write({'flow_state': response_data['flow_state'], 'data_buffer': response_data.get('data_buffer', '')})
            return self._send_response(response_data)
        
        # --- MANEJADOR UNIFICADO CON IA ---
        if intent in ["consulta_horario_direccion", "consulta_informativa", "otro", ""]:
            _logger.info(f"General Fallback/Info: Intención '{intent}' detectada. Enviando a handle_respuesta_faq.")
            faq_response = handle_respuesta_faq(self.env, self.partner, self.plain_text, conv)
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