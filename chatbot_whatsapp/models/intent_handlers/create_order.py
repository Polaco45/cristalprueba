import json
import logging
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# -----------------------
# Configuración de OpenAI
# -----------------------

def get_openai_api_key(env):
    return env['ir.config_parameter'].sudo().get_param('openai.api_key')

# Defino los schemas que OpenAI podrá invocar
FUNCTIONS = [
    {
        "name": "lookup_product_variants",
        "description": "Busca variantes de producto en Odoo",
        "parameters": {
            "type": "object",
            "properties": {
                "query": { "type": "string", "description": "Término de búsqueda libre" }
            },
            "required": ["query"]
        },
    },
    {
        "name": "create_sale_order",
        "description": "Crea un pedido de venta en borrador",
        "parameters": {
            "type": "object",
            "properties": {
                "partner_id": { "type": "integer" },
                "product_id": { "type": "integer" },
                "quantity": { "type": "integer" }
            },
            "required": ["partner_id", "product_id", "quantity"]
        }
    }
]

# -----------------------
# Funciones Odoo
# -----------------------

def lookup_product_variants(env, query, limit=5):
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"Lo siento, no hay stock disponible para '{query}'.")
    return [
        { 'id': v.id, 'name': v.display_name, 'stock': v.qty_available, 'price': v.list_price }
        for v in in_stock
    ]


def create_sale_order(env, partner_id, product_id, quantity):
    order = env['sale.order'].sudo().create({
        'partner_id': partner_id,
        'order_line': [(0, 0, {
            'product_id': product_id,
            'product_uom_qty': quantity,
            'price_unit': env['product.product'].browse(product_id).list_price,
        })]
    })
    return order

# -----------------------
# Manejo de petición
# -----------------------

def handle_crear_pedido(env, partner, text):
    openai.api_key = get_openai_api_key(env)

    system_msg = {"role": "system", "content": (
        "Eres un asistente que recibe pedidos de venta. "
        "Usa lookup_product_variants para buscar variantes y create_sale_order para crear pedidos."
    )}

    # Primer llamado: búsqueda del producto
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message

    if not msg.get('function_call'):
        _logger.error("No function_call en primera respuesta: %s", resp)
        return "Perdón, no entendí qué producto querés pedir."

    if msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error("Esperando lookup_product_variants, vino: %s", msg['function_call']['name'])
        return "Algo salió mal al procesar el producto."

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants_info = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # Segundo llamado: elegir variante y cantidad
    followup = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            system_msg,
            {"role": "user", "content": text},
            {"role": "function", "name": 'lookup_product_variants', "content": json.dumps(variants_info)}
        ],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )

    follow_msg = followup.choices[0].message

    if not follow_msg.get('function_call'):
        _logger.error("No function_call en followup: %s", followup)
        return "No entendí qué variante elegiste. ¿Podés indicar el producto y cantidad?"

    fn2 = follow_msg['function_call']
    args2 = json.loads(fn2['arguments'])
    product_id = args2.get('product_id')
    requested_qty = args2.get('quantity')

    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0

    if requested_qty > available:
        # Nueva conversación: proponer la cantidad máxima
        new_user_msg = f"El cliente pidió {requested_qty} unidades pero sólo hay {available}. ¿Querés pedir {available} unidades de '{variant.display_name}'?"
        confirm_resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                system_msg,
                {"role": "user", "content": text},
                {"role": "function", "name": 'lookup_product_variants', "content": json.dumps(variants_info)},
                follow_msg,
                {"role": "assistant", "content": f"Solo hay {available} unidades disponibles de '{variant.display_name}'. ¿Querés que cree un pedido por {available} unidades?"},
                {"role": "user", "content": "Sí, por favor."}
            ],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0
        )
        confirm_msg = confirm_resp.choices[0].message

        if not confirm_msg.get('function_call') or confirm_msg['function_call']['name'] != 'create_sale_order':
            _logger.error("No function_call o no es create_sale_order en confirmación: %s", confirm_resp)
            return f"Solo hay {available} unidades de '{variant.display_name}'. ¿Querés que cree un pedido por esa cantidad?"

        args3 = json.loads(confirm_msg['function_call']['arguments'])
        product_id = args3.get('product_id')
        requested_qty = args3.get('quantity')

    # Crear pedido final
    order = create_sale_order(env, partner.id, product_id, requested_qty)
    return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."
