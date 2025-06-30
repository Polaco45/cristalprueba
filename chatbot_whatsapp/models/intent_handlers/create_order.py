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
    return products_with_prices


def create_sale_order(env, partner_id, product_id, quantity):
    # Obtiene registros básicos
    partner = env['res.partner'].browse(partner_id)
    product = env['product.product'].browse(product_id)
    pricelist = partner.property_product_pricelist

    # Crea pedido de venta con línea
    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product_id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': quantity,
        })]
    })

    # Crea oportunidad (lead) vinculada al pedido
    lead_vals = {
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente sin nombre'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': (
            f"Se generó un pedido desde WhatsApp.\n"
            f"Producto: {product.display_name}\n"
            f"Cantidad: {quantity}"
        ),
        'expected_revenue': order.amount_total,
        'source_id': (env.ref('crm.source_website_leads', raise_if_not_found=False)
                    and env.ref('crm.source_website_leads').id),
    }

    lead = env['crm.lead'].sudo().create(lead_vals)

    # Vincula la orden a la oportunidad
    order.write({'opportunity_id': lead.id})

    # Crea actividad de seguimiento
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
    """
    ✅ FUNCIÓN SIMPLIFICADA: Solo maneja nuevos pedidos
    Los estados de memoria se manejan en el archivo principal
    """


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
        variants = lookup_product_variants(env, partner, args['query'], limit=20)
    except UserError as ue:
        return str(ue)

    # Extraer cantidad del texto si existe
    m = re.search(r'\b(\d+)\b', text)
    qty = int(m.group(1)) if m else None

    # Si hay muchas opciones, mostrar lista para selección
    if len(variants) >= 5:
        buttons = "\n".join([
            f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)
        ])

        # Guardar en memoria
        memory_model = env['chatbot.whatsapp.memory'].sudo()
        memory_payload = {
            'products': variants,
            'qty': qty
        }
        memory_model.create({
            'partner_id': partner.id,
            'last_intent': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload)
        })
        env.cr.flush()
        env.cr.commit()

        return (
            f"Tenemos varias opciones para {args['query']}:\n"
            f"{buttons}\n"
            "Respondé con el número o el nombre del producto que querés."
        )

    # Si solo hay una opción
    variant = variants[0]
    pid = variant['id']
    avail = int(variant['stock'])
    name = variant['name']

    memory_model = env['chatbot.whatsapp.memory'].sudo()
    existing_memory = memory_model.search([('partner_id', '=', partner.id)], limit=1)

    # Si no especificó cantidad, pedirla y guardar en memoria
    if not qty:
        if existing_memory:
            existing_memory.write({
                'last_intent': 'esperando_cantidad_producto',
                'last_variant_id': pid,
                'data_buffer': json.dumps({'product': variant})
            })
            env.cr.flush()
            env.cr.commit()
        else:
            memory_model.create({
                'partner_id': partner.id,
                'last_intent': 'esperando_cantidad_producto',
                'last_variant_id': pid,
                'data_buffer': json.dumps({'product': variant})
            })
            env.cr.flush()
            env.cr.commit()

        _logger.info(f"💾 Memoria creada/actualizada: esperando_cantidad_producto para producto {name} (ID: {pid})")
        return f'¡Perfecto! Elegiste "{name}". ¿Cuántas unidades querés?'

    # Si especificó cantidad pero no hay suficiente stock
    if qty > avail:
        if existing_memory:
            existing_memory.write({
                'last_intent': 'esperando_confirmacion_stock',
                'last_variant_id': pid,
                'last_qty_suggested': avail
            })
            env.cr.flush()
            env.cr.commit()
        else:
            memory_model.create({
                'partner_id': partner.id,
                'last_intent': 'esperando_confirmacion_stock',
                'last_variant_id': pid,
                'last_qty_suggested': avail
            })
            env.cr.flush()
            env.cr.commit()

        return (
            f'Solo hay {avail} unidades de "{name}".\n'
            'Respondé con:\n1) Sí\n2) Otra cantidad\n3) No'
        )

    # Todo perfecto: crear pedido directamente
    order = create_sale_order(env, partner.id, pid, qty)
    return f"📝 Pedido {order.name} creado: {qty}×{name}."