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

def create_sale_order(env, partner_id, product_id, quantity):
    partner = env['res.partner'].browse(partner_id)
    product = env['product.product'].browse(product_id)
    pricelist = partner.property_product_pricelist

    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product_id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': quantity,
        })]
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

def handle_crear_pedido(env, partner, text, send_buttons=None):
    _logger.info(f"📌 Evaluando intención CREAR_PEDIDO — Partner: {partner.name}")
    memory_model = env['chatbot.whatsapp.memory'].sudo()
    memory = memory_model.search([('partner_id', '=', partner.id)], order='timestamp desc', limit=1)

    if memory and memory.flow_state == 'esperando_cantidad_producto':
        try:
            qty = int(text.strip())
        except ValueError:
            _logger.warning("⚠️ No se pudo convertir el texto a cantidad.")
            return "No entendí la cantidad. ¿Podés escribir un número?"

        variant = memory.last_variant_id
        avail = variant.qty_available or 0

        _logger.info(f"🧮 Usuario respondió cantidad: {qty} — Stock disponible: {avail}")

        if qty > avail:
            memory.write({
                'flow_state': 'esperando_confirmacion_stock',
                'last_qty_suggested': avail
            })
            return f"Solo hay {avail} unidades de “{variant.display_name}”.\nRespondé con:\n1) Sí\n2) Otra cantidad\n3) No"

        order = create_sale_order(env, partner.id, variant.id, qty)
        memory.unlink()
        return f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}."

    # GPT busca producto
    openai.api_key = get_openai_api_key(env)
    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza. "
            "Cuando recibas un texto, devuelve un function_call 'lookup_product_variants' "
            "con el parámetro 'query' igual al nombre del producto solicitado."
        )
    }

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0,
        max_tokens=50
    )

    msg = resp.choices[0].message
    if msg.get('function_call', {}).get('name') != 'lookup_product_variants':
        _logger.warning("❌ GPT no devolvió una llamada válida a lookup_product_variants.")
        return "No entendí qué producto querés."

    args = json.loads(msg.function_call.arguments)
    _logger.info(f"🔧 GPT detectó intención de buscar producto: {args['query']}")

    try:
        variants = lookup_product_variants(env, partner, args['query'], limit=20)
    except UserError as ue:
        _logger.warning(f"⚠️ Error buscando variantes: {str(ue)}")
        return str(ue)

    m = re.search(r'\b(\d+)\b', text)
    qty = int(m.group(1)) if m else None

    if len(variants) >= 5:
        buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
        memory_payload = {'products': variants, 'qty': qty}
        memory_model.create({
            'partner_id': partner.id,
            'flow_state': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload)
        })
        _logger.info(f"📋 {len(variants)} opciones encontradas. Esperando selección de producto.")
        return f"Tenemos varias opciones para {args['query']}:\n{buttons}\nRespondé con el número o el nombre del producto que querés."

    variant = variants[0]
    pid = variant['id']
    name = variant['name']
    avail = int(variant['stock'])

    if not qty:
        memory_model.create({
            'partner_id': partner.id,
            'flow_state': 'esperando_cantidad_producto',
            'last_variant_id': pid,
            'data_buffer': json.dumps({'product': variant})
        })
        _logger.info(f"🟡 Esperando cantidad para producto único: {name}")
        return f"¡Perfecto! Elegiste “{name}”. ¿Cuántas unidades querés?"

    if qty > avail:
        memory_model.create({
            'partner_id': partner.id,
            'flow_state': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail
        })
        _logger.info(f"🟠 Stock insuficiente: {qty} solicitado > {avail} disponible")
        return f"Solo hay {avail} unidades de “{name}”.\nRespondé con:\n1) Sí\n2) Otra cantidad\n3) No"

    order = create_sale_order(env, partner.id, pid, qty)
    _logger.info(f"✅ Pedido directo generado: {qty}×{name}")
    return f"📝 Pedido {order.name} creado: {qty}×{name}."
