# ✅ create_order.py

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

def lookup_product_variants(env, query, limit=5):
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"No hay stock disponible para '{query}'.")

    partner = env.context.get('partner')
    pricelist = partner.property_product_pricelist if partner else None
    price_context = {'pricelist': pricelist.id} if pricelist else {}

    return [
        {
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': v.with_context(**price_context).price if price_context else v.list_price,
        }
        for v in in_stock
    ]

def suggest_ecommerce_categories(env, query):
    Product = env['product.template'].sudo()
    Category = env['product.public.category'].sudo()
    matched_products = Product.search([
        '|', ('name', 'ilike', query), ('description_sale', 'ilike', query)
    ])
    category_counts = {}
    for product in matched_products:
        for cat in product.public_categ_ids:
            if cat.id not in category_counts:
                category_counts[cat.id] = {'name': cat.name, 'count': 0, 'id': cat.id}
            category_counts[cat.id]['count'] += 1
    categories = sorted(category_counts.values(), key=lambda c: c['count'], reverse=True)
    return categories[:5]

def create_sale_order(env, partner_id, product_id, quantity):
    product = env['product.product'].browse(product_id)
    partner = env['res.partner'].browse(partner_id)
    pricelist = partner.property_product_pricelist

    lead = env['crm.lead'].sudo().create({
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente sin nombre'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': f"Se generó un pedido desde WhatsApp.\nProducto: {product.display_name}\nCantidad: {quantity}",
        'source_id': env.ref('crm.source_website_leads', raise_if_not_found=False) and env.ref('crm.source_website_leads').id,
    })

    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'opportunity_id': lead.id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product_id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': quantity,
        })]
    })

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
    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza.\n"
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
        return "No entendí qué producto querés."

    args = json.loads(msg.function_call.arguments)
    try:
        variants = lookup_product_variants(env.with_context(partner=partner), args['query'], limit=20)
    except UserError as ue:
        return str(ue)

    m = re.search(r'\b(\d+)\b', text)
    qty = int(m.group(1)) if m else None

    if len(variants) >= 5:
        buttons = "\n".join([
            f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)
        ])
        memory_payload = {
            'products': variants,
            'qty': qty
        }
        env['chatbot.whatsapp.memory'].sudo().create({
            'partner_id': partner.id,
            'last_intent': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload)
        })
        return (
            f"Tenemos varias opciones para {args['query']}:\n"
            f"{buttons}\n"
            "Respondé con el número o el nombre del producto que querés."
        )

    variant = variants[0]
    pid = variant['id']
    avail = int(variant['stock'])
    name = variant['name']

    if not qty:
        return f"¡Perfecto! Elegiste “{name}”. ¿Cuántas unidades querés?"

    if qty > avail:
        env['chatbot.whatsapp.memory'].sudo().create({
            'partner_id': partner.id,
            'last_intent': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail
        })
        return (
            f"Solo hay {avail} unidades de “{name}”.\n"
            "Respondé con:\n"
            f"1) Sí, quiero las {avail}\n"
            "2) Quiero otra cantidad\n"
            "3) No, gracias"
        )

    order = create_sale_order(env, partner.id, pid, qty)
    return f"📍 Pedido {order.name} creado: {qty}×{name}."
