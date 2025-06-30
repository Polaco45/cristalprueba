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
        raise UserError(f"No se encontraron productos para '{query}'")

    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"No hay stock disponible para '{query}'")

    pricelist = partner.property_product_pricelist
    order = SaleOrder.new({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
    })

    products_with_prices = []
    for v in in_stock:
        line = env['sale.order.line'].new({
            'order_id': order.id,
            'product_id': v.id,
            'product_uom_qty': 1.0,
            'product_uom': v.uom_id.id,
            'order_partner_id': partner.id,
        })
        line._onchange_product_id()
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
    # ... creación de oportunidad quedan igual ...
    return order


def handle_crear_pedido(env, partner, text, memory):
    _logger.info(f"📌 Evaluando intención CREAR_PEDIDO — Partner: {partner.name}")
    openai.api_key = get_openai_api_key(env)

    # Construir mensajes para OpenAI
    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza. "
            "Cuando recibas un texto, devuelve un function_call 'lookup_product_variants' "
            "con el parámetro 'query' igual al nombre del producto solicitado y 'quantity' si se especifica."
        )
    }
    current_cart = json.loads(memory.data_buffer or '{}').get('cart', [])
    if current_cart:
        cart_desc = ", ".join([f"{item['quantity']}x {item['name']}" for item in current_cart])
        system_msg['content'] += f"\nEl carrito actual contiene: {cart_desc}."

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[system_msg, {"role": "user", "content": text}],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0,
            max_tokens=200
        )
        msg = resp.choices[0].message
    except Exception as e:
        _logger.error(f"❌ Error en la llamada a OpenAI: {e}")
        return "Hubo un problema al procesar tu solicitud. Por favor, intentá de nuevo."

    # Recopilar llamadas detectadas
    tool_calls = []
    if hasattr(msg, 'function_call') and msg.function_call:
        tool_calls.append(msg.function_call)
    elif msg.get('tool_calls'):
        tool_calls.extend(msg.tool_calls)

    # Si GPT no generó llamada, fallback directo
    if not tool_calls:
        try:
            variants = lookup_product_variants(env, partner, text, limit=6)
        except UserError as ue:
            return f"No pude identificar ningún producto para agregar. {ue.args[0]}. ¿Podrías ser más específico?"
        # Múltiples variantes
        if len(variants) > 1:
            buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
            cart = current_cart
            memory.write({
                'flow_state': 'esperando_seleccion_producto',
                'data_buffer': json.dumps({'products': variants, 'qty': None, 'cart': cart}),
                'last_intent_detected': 'crear_pedido'
            })
            return f"Tenemos varias opciones para '{text}':\n{buttons}\nRespondé con el número del producto que querés."
        # Una sola variante encontrada
        variant = variants[0]
        pid, name, avail = variant['id'], variant['name'], int(variant['stock'])
        cart = current_cart
        # Si no hay cantidad en el texto, pedimos cantidad
        m = re.search(r'\b(\d+)\b', text)
        qty = int(m.group(1)) if m else None
        if not qty:
            memory.write({
                'flow_state': 'esperando_cantidad_producto',
                'last_variant_id': pid,
                'data_buffer': json.dumps({'product_name': name, 'product_id': pid, 'cart': cart}),
                'last_intent_detected': 'crear_pedido'
            })
            return f"¡Perfecto! Encontramos “{name}”. ¿Cuántas unidades querés?"
        if qty > avail:
            memory.write({
                'flow_state': 'esperando_confirmacion_stock',
                'last_variant_id': pid,
                'last_qty_suggested': avail,
                'data_buffer': json.dumps({'product_name': name, 'product_id': pid, 'cart': cart}),
                'last_intent_detected': 'crear_pedido'
            })
            return f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar"
        # Agregar directamente
        cart.append({'product_id': pid, 'quantity': qty, 'name': name})
        memory.write({
            'flow_state': 'pedido_en_progreso',
            'data_buffer': json.dumps({'cart': cart}),
            'last_variant_id': False,
            'last_qty_suggested': False,
            'last_intent_detected': 'crear_pedido'
        })
        return f"¡Perfecto! Agregamos {qty}x {name} a tu pedido. ¿Querés algo más?"

    # Procesar las llamadas de GPT si existen
    products_added = []
    cart = current_cart
    for call in tool_calls:
        if hasattr(call, 'function') and call.function.name == 'lookup_product_variants':
            args = json.loads(call.function.arguments)
            query, nlp_qty = args.get('query'), args.get('quantity')
            _logger.info(f"🔧 GPT detectó búsqueda: {query}, qty: {nlp_qty}")
            try:
                variants = lookup_product_variants(env, partner, query, limit=6)
            except UserError as ue:
                products_added.append(f"No stock para '{query}': {ue.args[0]}")
                continue
            qty = nlp_qty or (int(re.search(r'\b(\d+)\b', text).group(1)) if re.search(r'\b(\d+)\b', text) else None)
            if len(variants) > 1:
                buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
                memory.write({
                    'flow_state': 'esperando_seleccion_producto',
                    'data_buffer': json.dumps({'products': variants, 'qty': qty, 'cart': cart}),
                    'last_intent_detected': 'crear_pedido'
                })
                return f"Tenemos varias opciones para '{query}':\n{buttons}\nRespondé con el número del producto que querés."
            # Sola variante
            variant = variants[0]
            pid, name, avail = variant['id'], variant['name'], int(variant['stock'])
            if not qty:
                memory.write({
                    'flow_state': 'esperando_cantidad_producto',
                    'last_variant_id': pid,
                    'data_buffer': json.dumps({'product_name': name, 'product_id': pid, 'cart': cart}),
                    'last_intent_detected': 'crear_pedido'
                })
                return f"¡Perfecto! Encontramos “{name}”. ¿Cuántas unidades querés?"
            if qty > avail:
                memory.write({
                    'flow_state': 'esperando_confirmacion_stock',
                    'last_variant_id': pid,
                    'last_qty_suggested': avail,
                    'data_buffer': json.dumps({'product_name': name, 'product_id': pid, 'cart': cart}),
                    'last_intent_detected': 'crear_pedido'
                })
                return f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar"
            cart.append({'product_id': pid, 'quantity': qty, 'name': name})
            products_added.append(f"{qty}x {name}")
    if products_added:
        memory.write({
            'flow_state': 'pedido_en_progreso',
            'data_buffer': json.dumps({'cart': cart}),
            'last_variant_id': False,
            'last_qty_suggested': False,
            'last_intent_detected': 'crear_pedido'
        })
        if len(products_added) > 1:
            return "Agregamos los siguientes productos a tu pedido:\n" + "\n".join(products_added) + "\n¿Querés agregar algo más o finalizar?"
        return f"¡Perfecto! Agregamos {products_added[0]} a tu pedido. ¿Querés algo más?"

    # Si nada
    return "No pude identificar ningún producto para agregar. ¿Podrías ser más específico?"
