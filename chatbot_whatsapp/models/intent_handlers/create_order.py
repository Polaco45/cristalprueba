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
        "description": "Busca variantes de producto en Odoo a partir de un texto de usuario. Puede extraer múltiples productos.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string", "description": "El nombre del producto que busca el usuario."},
                            "quantity": {"type": "integer", "description": "La cantidad solicitada para ese producto, si se especifica."}
                        },
                        "required": ["product_name"]
                    }
                }
            },
            "required": ["queries"]
        },
    }
]

def lookup_product_variants(env, partner, query, limit=20):
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)

    if not variants:
        raise UserError(f"No se encontraron productos para '{query}'.")

    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"No hay stock disponible para '{query}'.")

    pricelist = partner.property_product_pricelist
    products_with_prices = []
    for v in in_stock:
        price = v.with_context(pricelist=pricelist.id).price
        products_with_prices.append({
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': price,
        })
    return products_with_prices

def create_sale_order(env, partner_id, order_lines):
    if not order_lines:
        return None
        
    partner = env['res.partner'].browse(partner_id)
    pricelist = partner.property_product_pricelist

    order_line_vals = []
    description_parts = ["Se generó un pedido desde WhatsApp:"]
    
    for line in order_lines:
        product = env['product.product'].browse(line['product_id'])
        order_line_vals.append((0, 0, {
            'product_id': line['product_id'],
            'product_uom': product.uom_id.id,
            'product_uom_qty': line['quantity'],
        }))
        description_parts.append(f"- {line['quantity']} x {product.display_name}")

    order = env['sale.order'].with_context(pricelist=pricelist.id).sudo().create({
        'partner_id': partner_id,
        'pricelist_id': pricelist.id,
        'order_line': order_line_vals
    })

    _logger.info(f"✅ Orden creada: {order.name} — ${order.amount_total:.2f}")

    lead_vals = {
        'name': f"Pedido WhatsApp: {partner.name or 'Cliente'}",
        'partner_id': partner_id,
        'type': 'opportunity',
        'description': "\n".join(description_parts),
        'expected_revenue': order.amount_total,
    }
    lead = env['crm.lead'].sudo().create(lead_vals)
    order.write({'opportunity_id': lead.id})

    activity_type = env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
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
    _logger.info(f"📌 Evaluando CREAR_PEDIDO para: {partner.name} | Texto: '{text}'")
    openai.api_key = get_openai_api_key(env)
    
    system_msg = {
        "role": "system",
        "content": "Eres un asistente para pedidos. Extrae los nombres de productos y sus cantidades del texto del usuario. Si un usuario pide 'un escobillon y un blem', extrae ambos. Devuelve un function_call a 'lookup_product_variants'."
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
        return "No entendí qué producto querés. ¿Podés ser más específico?"

    args = json.loads(msg.function_call.arguments)
    queries = args.get('queries', [])
    if not queries:
        return "No entendí qué producto querés."
    
    # Por simplicidad, manejamos el primer producto que se encuentre.
    # El bucle de "¿Algo más?" se encargará del resto.
    first_query = queries[0]
    product_name = first_query.get('product_name')
    qty = first_query.get('quantity')

    _logger.info(f"🔧 GPT detectó producto: '{product_name}' con cantidad: {qty}")

    try:
        variants = lookup_product_variants(env, partner, product_name, limit=6)
    except UserError as ue:
        return str(ue)

    if len(variants) > 1:
        buttons = "\n".join([f"{i+1}) {v['name']} - ${v['price']:.2f}" for i, v in enumerate(variants)])
        memory_payload = {'products': variants, 'qty': qty}
        memory.write({
            'flow_state': 'esperando_seleccion_producto',
            'data_buffer': json.dumps(memory_payload),
        })
        return f"Tenemos varias opciones para '{product_name}':\n{buttons}\nRespondé con el número del producto que querés."

    variant = variants[0]
    pid = variant['id']
    avail = int(variant['stock'])

    if not qty:
        memory.write({
            'flow_state': 'esperando_cantidad_producto',
            'last_variant_id': pid,
            'data_buffer': json.dumps({'product': variant}),
        })
        return f"¡Perfecto! Encontramos “{variant['name']}”. ¿Cuántas unidades querés?"

    if qty > avail:
        memory.write({
            'flow_state': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail,
            'data_buffer': json.dumps({'original_qty': qty})
        })
        return f"Solo hay {avail} unidades de “{variant['name']}”.\nRespondé con:\n1) Sí, agregar esa cantidad\n2) No, cancelar este producto"

    # Si todo está bien, no se devuelve mensaje. La lógica principal lo manejará.
    return {'product_id': pid, 'quantity': qty, 'name': variant['name']}