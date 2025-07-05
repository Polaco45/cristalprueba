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
    handle_agradecimiento_cierre, handle_consulta_producto
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

    def _send_text(self, text_to_send):
        _logger.info(f"🚀 Preparando para enviar mensaje: '{text_to_send}'")
        vals = {
            'mobile_number': self.record.mobile_number,
            'body': text_to_send,
            'state': 'outgoing',
            'wa_account_id': self.record.wa_account_id.id if self.record.wa_account_id else False,
            'create_uid': self.env.ref('base.user_admin').id,
        }
        outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
        outgoing_msg.sudo().write({'body': text_to_send})
        if hasattr(outgoing_msg, '_send_message'):
            outgoing_msg._send_message()
        _logger.info(f"✅ Mensaje '{outgoing_msg.id}' procesado para envío.")

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

    # --- MANEJADORES DE FLUJOS ESPECÍFICOS ---

    # --- MODIFICADO: Ahora verifica las direcciones antes de crear la orden ---
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
                
                # --- NUEVO: Formateo manual y limpio de la dirección ---
                address_lines = []
                for i, addr in enumerate(delivery_addresses):
                    # Se crea una lista con las partes de la dirección
                    parts = [
                        addr.name,
                        addr.street,
                        addr.city,
                        addr.state_id.name,
                        addr.zip,
                        addr.country_id.name
                    ]
                    # Se filtran las partes vacías y se unen con ", "
                    formatted_address = ", ".join(filter(None, parts))
                    address_lines.append(f"{i+1}) {formatted_address}")
                
                address_list_str = "\n".join(address_lines)
                
                self.memory.write({
                    'flow_state': 'esperando_seleccion_direccion',
                    'data_buffer': json.dumps({'addresses': delivery_addresses.ids})
                })
                
                # Se agrega una línea final para mayor claridad en la instrucción
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

    # --- NUEVO: Manejador para el flujo de selección de dirección ---
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

    # --- MODIFICADO: Lógica completamente nueva para el flujo de selección ---
    def _handle_flow_esperando_seleccion_producto(self):
        """
        Maneja la respuesta del usuario después de mostrarle una lista de productos.
        Ahora puede entender si el usuario selecciona, pregunta o cancela.
        """
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['product_selection_intent_system']
        sub_intent = detect_intention([{"role": "user", "content": self.plain_text}], api_key, system_prompt)
        
        _logger.info(f"🔎 Sub-intención detectada en selección: '{sub_intent}'")

        if sub_intent == 'seleccionar_producto':
            try:
                data = json.loads(self.memory.data_buffer or '{}')
                variants, qty = data.get('products', []), data.get('qty')
                
                selected_variant = None
                # Intenta extraer un número del texto del usuario
                match = re.search(r'\d+', self.plain_text)
                if match:
                    index = int(match.group(0)) - 1
                    if 0 <= index < len(variants):
                        selected_variant = variants[index]

                # Si no se encontró por número, intenta por nombre (esto es opcional y se puede quitar si causa problemas)
                if not selected_variant:
                    for v in variants:
                        if v['name'].lower() in self.plain_text.lower():
                             selected_variant = v
                             break
                
                if not selected_variant:
                    return self._send_text(messages_config['invalid_option'])

                # Si llegamos aquí, se seleccionó un producto. Continuamos el flujo.
                self.memory.write({'data_buffer': json.dumps({'pending_products': data.get('original_queue', [])})})
                pid, name, avail = selected_variant['id'], selected_variant['name'], int(selected_variant['stock'])

                if not qty:
                    self.memory.write({
                        'flow_state': 'esperando_cantidad_producto', 
                        'last_variant_id': pid, 
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
            except (ValueError, json.JSONDecodeError) as e:
                _logger.error(f"Error procesando selección de producto: {e}")
                self.memory.write({'flow_state': False, 'data_buffer': ''})
                return self._send_text(messages_config['error_processing'])

        elif sub_intent == 'nueva_consulta':
            # El usuario hizo otra pregunta, rompemos el flujo actual y lo tratamos como una nueva consulta.
            _logger.info("El usuario hizo una nueva consulta, rompiendo el flujo de selección.")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._handle_general_intent()
        
        elif sub_intent == 'cancelar_seleccion':
            # El usuario no quiere ninguna de las opciones.
            _logger.info("El usuario canceló la selección de producto.")
            self.memory.write({'flow_state': False, 'data_buffer': ''})
            return self._send_text(messages_config['selection_cancelled'])

        else:
            # Fallback por si la sub-intención no es clara
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
            
    # --- MANEJADORES DE INTENCIONES ---

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
        
        # --- MODIFICADO: Se separa `consulta_producto` para un manejo especial ---
        
        # Manejadores que devuelven solo texto
        simple_handlers = {
            "saludo": lambda: handle_saludo(self.env, self.partner),
            "agradecimiento_cierre": lambda: handle_agradecimiento_cierre(self.env, self.partner, self.plain_text),
            "solicitar_factura": lambda: handle_solicitar_factura(self.partner, self.plain_text).get('message'),
        }

        if intent in simple_handlers:
            response_message = simple_handlers[intent]()
            return self._send_text(response_message)

        # Manejadores que inician un flujo de pedido
        if intent == "crear_pedido":
            return self._handle_crear_pedido_intent()
        if intent == "modificar_pedido":
            return self._send_text(handle_modificar_pedido(self.env, self.memory))

        # --- NUEVO: Manejo especial para consulta_producto que devuelve un dict ---
        if intent == "consulta_producto":
            response_data = handle_consulta_producto(self.env, self.partner, self.plain_text)
            
            # Si el handler preparó un nuevo estado de flujo, lo guardamos
            if response_data.get('flow_state'):
                self.memory.write({
                    'flow_state': response_data['flow_state'],
                    'data_buffer': response_data['data_buffer']
                })
            
            return self._send_text(response_data['message'])

        # Fallback para el resto de las FAQs
        faq_response = handle_respuesta_faq(intent, self.partner, self.plain_text)
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