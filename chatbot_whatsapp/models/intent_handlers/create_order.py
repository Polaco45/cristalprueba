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
                "query": {"type": "string", "description": "Término de búsqueda libre"}
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
        line._onchange_product()
        products_with_prices.append({
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': line.price_unit,
        })

    _logger.info(f"📦 Variantes en stock: {[p['name'] for p in products_with_prices]}")
    return products_with_prices

def create_sale_order(env, partner_id, product_id=None, quantity=None, cart=None):
    """Si cart es lista de dicts, ignora product_id/quantity."""
    SaleOrder = env['sale.order'].sudo()
    partner = env['res.partner'].browse(partner_id)
    pricelist = partner.property_product_pricelist

    if cart:
        lines = [(0,0,{
            'product_id': item['id'],
            'product_uom_qty': item['qty'],
            'product_uom': env['product.product'].browse(item['id']).uom_id.id,
        }) for item in cart]
    else:
        lines = [(0,0,{
            'product_id': product_id,
            'product_uom_qty': quantity,
            'product_uom': env['product.product'].browse(product_id).uom_id.id,
        })]

    order = SaleOrder.with_context(pricelist=pricelist.id).create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': lines
    })

    _logger.info(f"✅ Orden creada: {order.name} — {quantity}×{product.display_name} — ${order.amount_total:.2f}")

    lead_vals = {
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente sin nombre'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': f"Se generó un pedido desde WhatsApp.\nProducto: {product.display_name}\nCantidad: {quantity}",
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

def handle_crear_pedido(env, partner, text, memory): # <-- Pasamos el registro de memoria
    """
    Manejador principal para la intención 'crear_pedido'.
    Esta función ahora se enfoca en iniciar el flujo de pedido.
    """
    _logger.info(f"📌 Evaluando intención CREAR_PEDIDO — Partner: {partner.name}")

    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza. "
            "Cuando recibas un texto, devuelve un function_call 'lookup_product_variants' "
            "con el parámetro 'query' igual al nombre del producto solicitado."
        )
    }

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[system_msg, {"role": "user", "content": text}],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0,
            max_tokens=50
        )
        msg = response.choices[0].message
    except Exception as e:
        _logger.error(f"❌ Error en la llamada a OpenAI: {e}")
        return "Hubo un problema al procesar tu solicitud. Por favor, intentá de nuevo."

    if msg.get('function_call', {}).get('name') != 'lookup_product_variants':
        _logger.warning("❌ GPT no devolvió una llamada válida a lookup_product_variants.")
        return "No entendí qué producto querés. ¿Podés ser más específico?"

    args = json.loads(msg.function_call.arguments)
    query = args.get('query')
    if not query:
        return "No entendí qué producto querés."

    _logger.info(f"🔧 GPT detectó intención de buscar producto: {query}")

    try:
        variants = lookup_product_variants(env, partner, query, limit=6)
    except UserError as ue:
        _logger.warning(f"⚠️ Error buscando variantes: {str(ue)}")
        return str(ue)

    # Intentamos detectar cantidad en el mismo mensaje
    match = re.search(r'\b(\d+)\b', text)
    qty = int(match.group(1)) if match else None

    # Si hay varias variantes, pedimos elegir una
    if len(variants) > 1:
        options = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
        payload = {
            'products': variants,
            'qty': qty,
        }
        memory.write({
            'flow_state': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(payload),
            'last_intent_detected': 'crear_pedido',
        })
        _logger.info(f"🧠 Memoria actualizada: esperando selección, {len(variants)} opciones, qty={qty}")
        return f"Tenemos varias opciones para '{query}':\n{options}\nRespondé con el número del producto que querés."

    # Si hay una sola variante
    variant = variants[0]
    pid = variant['id']
    name = variant['name']
    stock = int(variant['stock'])

    if not qty:
        # Si no se indicó cantidad, pedimos
        payload = {
            'product': variant
        }
        memory.write({
            'flow_state': 'esperando_cantidad_producto',
            'last_variant_id': pid,
            'data_buffer': json.dumps(payload),
            'last_intent_detected': 'crear_pedido',
        })
        _logger.info(f"🟡 Esperando cantidad para '{name}'")
        return f"¡Perfecto! Encontramos “{name}”. ¿Cuántas unidades querés?"

    if qty > stock:
        # Si no hay suficiente stock
        memory.write({
            'flow_state': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': stock,
            'last_intent_detected': 'crear_pedido',
        })
        _logger.info(f"🟠 Stock insuficiente: {qty} solicitado > {stock} disponible")
        return f"Solo hay {stock} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar"

    # Si hay suficiente stock: lo agregamos al carrito
    cart_item = {'id': pid, 'name': name, 'qty': qty}

    try:
        data = json.loads(memory.data_buffer or '{}')
    except Exception:
        data = {}

    cart = data.get('cart', [])
    cart.append(cart_item)

    # Guardamos el carrito actualizado en memoria
    memory.write({
        'flow_state': 'esperando_mas_producto',
        'data_buffer': json.dumps({'cart': cart}),
        'last_variant_id': False,
        'last_qty_suggested': False,
        'last_intent_detected': 'crear_pedido',
    })

    _logger.info(f"🛒 Producto agregado al carrito: {qty}×{name}")
    return f"Agregué {qty}×“{name}” al carrito. ¿Querés algo más?"
