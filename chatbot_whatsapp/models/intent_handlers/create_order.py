import json
import logging
import re
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def get_openai_api_key(env):
    return env['ir.config_parameter'].sudo().get_param('openai.api_key')

FUNCTIONS = [
    {
        "name": "lookup_product_variants",
        "description": "Busca variantes de producto en Odoo",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda libre"},
                "quantity": {"type": "integer", "description": "Cantidad del producto solicitado, si se especifica"},
            },
            "required": ["query"]
        },
    }
]

def lookup_product_variants(env, partner, query, limit=20):
    Product = env['product.product'].sudo()
    SaleOrder = env['sale.order'].sudo()
    SaleOrderLine = env['sale.order.line'].sudo()

    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)

    _logger.info(f"🔍 Buscando variantes para query '{query}' — Encontradas: {len(variants)}")

    if not variants:
        raise UserError(f"No se encontraron productos para '{query}'.")

    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"No hay stock disponible para '{query}'.")

    pricelist = partner.property_product_pricelist
    order = SaleOrder.new({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
    })

    products_with_prices = []
    for v in in_stock:
        line = SaleOrderLine.new({
            'order_id': order.id,
            'product_id': v.id,
            'product_uom_qty': 1.0,
            'product_uom': v.uom_id.id,
            'order_partner_id': partner.id,
        })
        line._onchange_product_id() # Use _onchange_product_id for product related calculations
        products_with_prices.append({
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': line.price_unit,
        })

    _logger.info(f"📦 Variantes en stock: {[p['name'] for p in products_with_prices]}")
    return products_with_prices

def create_sale_order_from_cart(env, partner_id, cart_items):
    partner = env['res.partner'].browse(partner_id)
    pricelist = partner.property_product_pricelist

    order_lines = []
    for item in cart_items:
        product = env['product.product'].browse(item['product_id'])
        order_lines.append((0, 0, {
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': item['quantity'],
        }))
    
    if not order_lines:
        raise UserError("No hay artículos en el carrito para crear un pedido.")

    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': order_lines
    })

    _logger.info(f"✅ Orden creada desde carrito: {order.name} — Total: ${order.amount_total:.2f}")

    lead_vals = {
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente sin nombre'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': f"Se generó un pedido desde WhatsApp con los siguientes artículos:\n" + 
                       "\n".join([f"- {item['quantity']}x {item['name']}" for item in cart_items]),
        'expected_revenue': order.amount_total,
        'source_id': (env.ref('crm.source_website_leads', raise_if_not_found=False)
                      and env.ref('crm.source_website_leads').id),
    }

    lead = env['crm.lead'].sudo().create(lead_vals)
    order.write({'opportunity_id': lead.id})

    activity_type = env['mail.activity.type'].sudo().search([
        ('name', 'ilike', 'Iniciativa de Venta')
    ], limit=1)

    if activity_type:
        env['mail.activity'].sudo().create({
            'res_model_id': env['ir.model']._get_id('crm.lead'),
            'res_id': lead.id,
            'activity_type_id': activity_type.id,
            'summary': 'Seguimiento pedido desde WhatsApp',
            'note': f"Revisar el pedido {order.name} para contacto con el cliente.",
            'user_id': partner.user_id.id or env.user.id,
        })

    return order

def handle_crear_pedido(env, partner, text, memory):
    """
    Manejador principal para la intención 'crear_pedido'.
    Esta función ahora agrega productos al carrito o inicia el flujo.
    """
    _logger.info(f"📌 Evaluando intención CREAR_PEDIDO — Partner: {partner.name}")

    openai.api_key = get_openai_api_key(env)
    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza. "
            "Cuando recibas un texto, devuelve un function_call 'lookup_product_variants' "
            "con el parámetro 'query' igual al nombre del producto solicitado y 'quantity' si se especifica. "
            "Si se nombran varios productos, haz múltiples llamadas a la función 'lookup_product_variants' si es posible, una por cada producto identificado."
        )
    }

    messages = [system_msg, {"role": "user", "content": text}]
    
    # Include current cart items in the system message for context, if any
    current_cart = json.loads(memory.data_buffer or '{}').get('cart', [])
    if current_cart:
        cart_description = ", ".join([f"{item['quantity']}x {item['name']}" for item in current_cart])
        messages[0]['content'] += f"\nEl carrito actual del cliente contiene: {cart_description}."

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0,
            max_tokens=200 # Increased max_tokens for multiple function calls
        )
        msg = resp.choices[0].message
    except Exception as e:
        _logger.error(f"❌ Error en la llamada a OpenAI: {e}")
        return "Hubo un problema al procesar tu solicitud. Por favor, intentá de nuevo."
    
    # Initialize cart from memory or as empty
    cart = json.loads(memory.data_buffer or '{}').get('cart', [])
    
    products_added_this_turn = []
    
    # --- RÓBUSTA GESTIÓN DE tool_calls ---
    # Prioritize tool_calls (newer OpenAI API structure for multiple calls)
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        tool_calls = msg.tool_calls
    # Fallback to function_call (older structure, typically for a single call)
    elif hasattr(msg, 'function_call') and msg.function_call:
        tool_calls = [msg.function_call] # Wrap single function_call in a list for consistent processing
    else:
        _logger.info("ℹ️ No se detectó ninguna llamada a función en la respuesta de OpenAI.")
        return "No pude identificar el producto que estás buscando. ¿Podrías ser más específico?"


    for tool_call in tool_calls:
        # Ensure 'function' attribute exists before accessing it
        if not hasattr(tool_call, 'function'):
            _logger.warning(f"❌ tool_call object missing 'function' attribute: {tool_call}")
            continue

        if tool_call.function.name == 'lookup_product_variants':
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                _logger.error(f"❌ Error decodificando argumentos de función: {e} - Arguments: {tool_call.function.arguments}")
                products_added_this_turn.append("No pude procesar el producto debido a un error de formato.")
                continue

            query = args.get('query')
            qty_from_nlp = args.get('quantity') # Quantity detected by NLP

            if not query:
                _logger.warning("❌ GPT no devolvió un query válido para lookup_product_variants.")
                continue
            
            _logger.info(f"🔧 GPT detectó intención de buscar producto: {query}, con cantidad: {qty_from_nlp}")

            try:
                variants = lookup_product_variants(env, partner, query, limit=6)
            except UserError as ue:
                _logger.warning(f"⚠️ Error buscando variantes: {str(ue)}")
                products_added_this_turn.append(f"No se encontró stock para '{query}': {str(ue)}")
                continue
            
            # If NLP provided a quantity, use it. Otherwise, try to extract from original text (fallback)
            qty = qty_from_nlp 
            if not qty:
                m = re.search(r'\b(\d+)\b', text)
                qty = int(m.group(1)) if m else None

            if len(variants) > 1:
                # If multiple variants, we need to ask the user to select
                buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
                memory_payload = {'products': variants, 'qty': qty, 'cart': cart} # Pass existing cart
                
                memory.write({
                    'flow_state': 'esperando_seleccion_producto',
                    'data_buffer': json.dumps(memory_payload),
                    'last_intent_detected': 'crear_pedido'
                })
                _logger.info(f"🧠 Guardando memoria: flow='esperando_seleccion_producto', productos={len(variants)}, qty={qty}, cart={len(cart)} items")
                return f"Tenemos varias opciones para '{query}'. Por favor, indicá el número de la opción que deseás:\n{buttons}"
            
            elif len(variants) == 1:
                selected_variant = variants[0]
                variant_obj = env['product.product'].sudo().browse(selected_variant['id'])
                avail = variant_obj.qty_available or 0

                # Determine final quantity
                final_qty = qty if qty is not None and qty > 0 else 1 # Default to 1 if no quantity specified

                if final_qty > avail:
                    memory.write({
                        'flow_state': 'esperando_confirmacion_stock',
                        'last_variant_id': variant_obj.id,
                        'last_qty_suggested': avail,
                        'data_buffer': json.dumps({'cart': cart}) # Preserve existing cart for later merge
                    })
                    return f"Solo hay {avail} unidades de “{variant_obj.display_name}”. ¿Querés llevar esa cantidad? (Sí/No)"
                else:
                    # Add item to cart
                    cart.append({'product_id': variant_obj.id, 'quantity': final_qty, 'name': variant_obj.display_name})
                    products_added_this_turn.append(f"{final_qty}x {variant_obj.display_name}")
                    memory.write({
                        'flow_state': 'pedido_en_progreso',
                        'data_buffer': json.dumps({'cart': cart}),
                        'last_variant_id': False,
                        'last_qty_suggested': False
                    })
            else: # No variants found (should be caught by UserError, but as a safeguard)
                products_added_this_turn.append(f"No se encontró el producto '{query}'.")
                
    if products_added_this_turn:
        if memory.flow_state == 'pedido_en_progreso':
            return f"Agregamos al carrito: {', '.join(products_added_this_turn)}. ¿Querés agregar algo más o finalizar tu pedido?"
        else:
            # This case means a product was added, but the flow wasn't 'pedido_en_progreso' before.
            # This might happen if the user jumps directly to "I want 3 items".
            # We transition to 'pedido_en_progreso' here.
            memory.write({'flow_state': 'pedido_en_progreso', 'data_buffer': json.dumps({'cart': cart})})
            return f"Agregamos al carrito: {', '.join(products_added_this_turn)}. ¿Querés agregar algo más o finalizar tu pedido?"
    else:
        # If no products were added and no specific error, it implies the NLP didn't find clear product info
        _logger.warning("No se pudo agregar ningún producto en handle_crear_pedido.")
        # If the flow is already 'pedido_en_progreso', prompt to add or finalize
        if memory.flow_state == 'pedido_en_progreso':
            return "No pude identificar el producto o la cantidad. Por favor, sé más específico. ¿Querés agregar algo más o finalizar tu pedido?"
        else:
            # If not in pedido_en_progreso, it's a general request to create an order
            memory.write({'flow_state': False, 'data_buffer': ''}) # Reset if NLP couldn't extract product
            return "Para crear un pedido, por favor indicá el producto y la cantidad que deseás."