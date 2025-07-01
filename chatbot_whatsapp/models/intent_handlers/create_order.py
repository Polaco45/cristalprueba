import json
import logging
import re
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# --- NUEVA FUNCIÓN HELPER ---
def add_item_to_cart(memory, product_id, quantity):
    """
    Agrega un item al carrito en la memoria.
    Si el producto ya existe, suma la cantidad. Si no, lo agrega como una nueva línea.
    """
    cart_items = json.loads(memory.pending_order_lines or '[]')
    
    found = False
    for item in cart_items:
        if item.get('product_id') == product_id:
            item['quantity'] += quantity
            found = True
            break
            
    if not found:
        cart_items.append({'product_id': product_id, 'quantity': quantity})
        
    memory.write({'pending_order_lines': json.dumps(cart_items)})
    _logger.info(f"🛒 Carrito actualizado: {cart_items}")

def get_openai_api_key(env):
    return env['ir.config_parameter'].sudo().get_param('openai.api_key')

FUNCTIONS = [
    {
        "name": "lookup_product_variants",
        "description": "Busca variantes de producto en Odoo a partir de un texto de usuario.",
        "parameters": {
            "type": "object",
            "properties": {
                "products": {
                    "type": "array",
                    "description": "Una lista de productos que el usuario mencionó.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "El nombre del producto a buscar."},
                            "quantity": {"type": "integer", "description": "La cantidad solicitada del producto."}
                        },
                        "required": ["query"]
                    }
                }
            },
            "required": ["products"]
        },
    }
]

def _format_cart_for_display(env, cart_lines):
    """Función helper para formatear el carrito y mostrarlo al usuario."""
    if not cart_lines:
        return "Tu carrito está vacío."

    product_ids = [item['product_id'] for item in cart_lines]
    products = env['product.product'].sudo().browse(product_ids)
    product_map = {p.id: p.display_name for p in products}

    summary_lines = []
    for i, item in enumerate(cart_lines, 1):
        product_name = product_map.get(item['product_id'], 'Producto no encontrado')
        summary_lines.append(f"{i}) {item['quantity']} × {product_name}")
    
    return "\n".join(summary_lines)


def handle_modificar_pedido(env, memory):
    """Prepara el mensaje para mostrar el carrito y permitir la eliminación."""
    cart_lines = json.loads(memory.pending_order_lines or '[]')

    if not cart_lines:
        memory.write({'flow_state': False})
        return "Tu carrito de compras está vacío. ¿Qué producto querés agregar?"

    cart_summary = _format_cart_for_display(env, cart_lines)
    
    memory.write({'flow_state': 'esperando_seleccion_eliminar'})
    
    response_message = (
        "Este es tu pedido actual:\n"
        f"{cart_summary}\n\n"
        "Respondé con el número del producto que querés eliminar, o escribí *cancelar* para volver."
    )
    return response_message


def lookup_product_variants(env, partner, query, limit=20):
    Product = env['product.product'].sudo()

    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)

    _logger.info(f"🔍 Buscando variantes para query '{query}' — Encontradas: {len(variants)}")

    if not variants:
        raise UserError(f"No encontramos ningún producto que coincida con '{query}'.")

    in_stock = variants.filtered(lambda p: (p.qty_available or 0) > 0)
    
    if not in_stock:
        raise UserError(f"Lo sentimos, no hay stock disponible para '{query}'.")

    pricelist = partner.property_product_pricelist
    if not pricelist:
        raise UserError("El cliente no tiene una tarifa asignada.")

    products_with_prices = []
    
    products_prices = pricelist._compute_price_rule(in_stock, 1.0)

    for v in in_stock:
        price = products_prices.get(v.id, (v.list_price, False))[0]
        
        products_with_prices.append({
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': price,
        })

    _logger.info(f"📦 Variantes en stock con precio: {[p['name'] for p in products_with_prices]}")
    return products_with_prices

def create_sale_order(env, partner_id, order_lines):
    partner = env['res.partner'].browse(partner_id)
    pricelist = partner.property_product_pricelist

    order_line_vals = []
    description_lines = []
    for line in order_lines:
        product = env['product.product'].browse(line['product_id'])
        order_line_vals.append((0, 0, {
            'product_id': line['product_id'],
            'product_uom': product.uom_id.id,
            'product_uom_qty': line['quantity'],
        }))
        description_lines.append(f"  - Producto: {product.display_name}, Cantidad: {line['quantity']}")

    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': order_line_vals
    })

    _logger.info(f"✅ Orden creada: {order.name} — {len(order_lines)} productos — ${order.amount_total:.2f}")

    lead_vals = {
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente sin nombre'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': "Se generó un pedido desde WhatsApp con los siguientes items:\n" + "\n".join(description_lines),
        'expected_revenue': order.amount_total,
    }
    lead = env['crm.lead'].sudo().create(lead_vals)
    order.write({'opportunity_id': lead.id})

    activity_type_id = env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
    if activity_type_id:
        env['mail.activity'].sudo().create({
            'res_model_id': env['ir.model']._get_id('crm.lead'),
            'res_id': lead.id,
            'activity_type_id': activity_type_id.id,
            'summary': 'Seguimiento pedido desde WhatsApp',
            'note': f"Revisar el pedido {order.name} para contacto con el cliente.",
            'user_id': partner.user_id.id or env.user.id,
        })

    return order

def handle_crear_pedido(env, partner, text, memory):
    _logger.info(f"📌 Evaluando CREAR_PEDIDO — Partner: {partner.name} — Texto: '{text}'")
    openai.api_key = get_openai_api_key(env)
    
    cart_items = json.loads(memory.pending_order_lines or '[]')
    context_info = "El usuario ya tiene productos en su carrito." if cart_items else "El carrito del usuario está vacío."

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos. Extrae los productos y cantidades del texto del usuario. "
            f"Contexto actual: {context_info}."
            "Usa la función 'lookup_product_variants' para CADA producto que identifiques. "
            "Si el usuario NO especifica una cantidad, OMITE el campo 'quantity' en tu respuesta."
        )
    }

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[system_msg, {"role": "user", "content": text}],
            functions=FUNCTIONS,
            function_call={"name": "lookup_product_variants"},
            temperature=0,
        )
        msg = resp.choices[0].message
    except Exception as e:
        _logger.error(f"❌ Error en la llamada a OpenAI: {e}")
        return "Hubo un problema al procesar tu solicitud. Por favor, intentá de nuevo."

    if not msg.get('function_call'):
        _logger.warning("❌ GPT no devolvió una llamada a función.")
        return "No entendí qué producto querés. ¿Podés ser más específico?"

    args = json.loads(msg.function_call.arguments)
    products_to_add = args.get('products', [])
    
    if not products_to_add:
        return "No pude identificar ningún producto en tu mensaje. ¿Podés intentarlo de nuevo?"

    first_product = products_to_add[0]
    query = first_product.get('query')
    qty = first_product.get('quantity')

    _logger.info(f"🔧 GPT detectó producto: {query} (Cantidad: {qty})")

    try:
        variants = lookup_product_variants(env, partner, query, limit=6)
    except UserError as ue:
        _logger.warning(f"⚠️ Error buscando variantes: {str(ue)}")
        return str(ue)

    if len(variants) > 1:
        buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
        memory_payload = {'products': variants, 'qty': qty}
        memory.write({
            'flow_state': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload),
        })
        _logger.info(f"🧠 Pidiendo clarificación para '{query}'")
        return f"Tenemos varias opciones para '{query}':\n{buttons}\nRespondé con el número del producto que querés."

    variant = variants[0]
    pid = variant['id']
    name = variant['name']
    avail = int(variant['stock'])

    if not qty:
        memory.write({
            'flow_state': 'esperando_cantidad_producto',
            'last_variant_id': pid,
            'data_buffer': json.dumps({'product': variant}),
        })
        _logger.info(f"🟡 Esperando cantidad para: {name}")
        return f"¡Perfecto! Encontramos “{name}”. ¿Cuántas unidades querés?"

    if qty <= avail:
        # --- MODIFICACIÓN ---
        # Se reemplaza la lógica de 'append' por la nueva función centralizada
        add_item_to_cart(memory, pid, qty)
        memory.write({'flow_state': 'esperando_confirmacion_pedido'})
        return f"👍 Agregado: {qty}×{name}.\n¿Querés agregar algo más?"
    else:
        memory.write({
            'flow_state': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail,
        })
        _logger.info(f"🟠 Stock insuficiente para {name}: {qty} solicitado > {avail} disponible")
        return f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí, esa cantidad\n2) No, cancelar"