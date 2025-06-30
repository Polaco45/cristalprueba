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
    """
    ✅ FUNCIÓN SIMPLIFICADA: Ahora primero chequea si estamos 'esperando_cantidad' en memoria.
    """
    memory_model = env['chatbot.whatsapp.memory'].sudo()
    existing_memory = memory_model.search([('partner_id', '=', partner.id)], limit=1)

    # 1) Si la memoria indica que estamos esperando cantidad, la procesamos acá y retornamos
    if existing_memory and existing_memory.last_intent == 'esperando_cantidad_producto':
        # Intentar parsear la cantidad
        try:
            qty = int(text.strip())
        except ValueError:
            return "No entendí la cantidad. ¿Podés escribir un número?"
        variant = existing_memory.last_variant_id
        avail = variant.qty_available or 0

        if qty > avail:
            existing_memory.write({
                'last_intent': 'esperando_confirmacion_stock',
                'last_qty_suggested': avail
            })
            # No borramos la memoria, pedimos confirmación
            return (
                f'Solo hay {avail} unidades de "{variant.display_name}".\n'
                'Respondé con:\n'
                '1) Sí\n'
                '2) Otra cantidad\n'
                '3) No'
            )

        # Todo ok: creamos pedido y limpiamos memoria
        order = create_sale_order(env, partner.id, variant.id, qty)
        existing_memory.unlink()
        return f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}."

    # 2) Si no estamos esperando cantidad, hacemos la búsqueda de producto normalmente
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
    _logger.warning("🔍 RESPUSTA DE OPENAI:")
    _logger.warning(json.dumps(resp.to_dict_recursive(), indent=2, ensure_ascii=False))

    msg = resp.choices[0].message
    # Si OpenAI no llamó a la función de lookup, esto es un fallo de comprensión
    if msg.get('function_call', {}).get('name') != 'lookup_product_variants':
        return "No entendí qué producto querés."

    # Parsear argumentos y buscar variantes
    args = json.loads(msg.function_call.arguments)
    try:
        variants = lookup_product_variants(env, partner, args['query'], limit=20)
    except UserError as ue:
        return str(ue)

    # Extraer cantidad directa (por si el usuario dijo "Blem 3")
    m = re.search(r'\b(\d+)\b', text)
    qty = int(m.group(1)) if m else None

    # 3) Si hay muchas variantes, mostramos botones y guardamos memoria de selección
    if len(variants) >= 5:
        buttons = "\n".join([
            f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)
        ])
        memory_payload = {'products': variants, 'qty': qty}
        memory_model.create({
            'partner_id': partner.id,
            'last_intent': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload)
        })
        return (
            f"Tenemos varias opciones para '{args['query']}':\n"
            f"{buttons}\n"
            "Respondé con el número o el nombre del producto que querés."
        )

    # 4) Si solo hay una variante, preguntamos cantidad (o continuamos si ya la detectó)
    variant = variants[0]
    pid = variant['id']
    avail = int(variant['stock'])
    name = variant['name']

    # Si no había cantidad detectada, guardamos memoria y preguntamos
    if not qty:
        memory_model.create({
            'partner_id': partner.id,
            'last_intent': 'esperando_cantidad_producto',
            'last_variant_id': pid,
            'data_buffer': json.dumps({'product': variant})
        })
        return f'¡Perfecto! Elegiste "{name}". ¿Cuántas unidades querés?'

    # Si sí detectó cantidad y hay stock suficiente
    if qty > avail:
        memory_model.create({
            'partner_id': partner.id,
            'last_intent': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail
        })
        return (
            f'Solo hay {avail} unidades de "{name}".\n'
            'Respondé con:\n'
            '1) Sí\n'
            '2) Otra cantidad\n'
            '3) No'
        )

    # Directamente creamos el pedido
    order = create_sale_order(env, partner.id, pid, qty)
    return f"📝 Pedido {order.name} creado: {qty}×{name}."
