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

# Memoria de confirmaciones pendientes: partner_id -> {'product_id', 'quantity'}
PENDING_CONFIRMATIONS = {}

# -----------------------
# Funciones Odoo
# -----------------------

def lookup_product_variants(env, query, limit=5):
    """
    Devuelve hasta `limit` variantes que coincidan con `query` y tengan stock (>0).
    """
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
    """
    Crea pedido en borrador para la variante indicada.
    """
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
    """
    Extrae intención con OpenAI y maneja stock y confirmaciones:
    - Si hay confirmación pendiente y usuario confirma, crea el pedido.
    - No stock: informa.
    - Cantidad > stock: propone stock máximo y espera confirmación.
    - OK: crea pedido.
    """
    openai.api_key = get_openai_api_key(env)
    user_text = text.strip().lower()

    # 1) Manejo de confirmación simple
    if partner.id in PENDING_CONFIRMATIONS and user_text in ['si', 'sí', 'ok', 'dale']:
        pending = PENDING_CONFIRMATIONS.pop(partner.id)
        order = create_sale_order(env, partner.id, pending['product_id'], pending['quantity'])
        return f"📝 Pedido {order.name} creado: {pending['quantity']}×{env['product.product'].browse(pending['product_id']).display_name}."

    # Prompt de sistema más explícito
    system_msg = {"role": "system", "content": (
        "Eres un asistente para pedidos de productos de limpieza. "
        "Primero usa lookup_product_variants para buscar variantes con stock. "
        "Luego, si la cantidad solicitada está disponible, llama a create_sale_order. "
        "Si no, informa al usuario la cantidad máxima y espera confirmación. "
        "Siempre devuelve un function_call cuando tengas todos los datos necesarios."
    )}

    # 2) Llamada inicial para buscar variantes
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message

    if not msg.get('function_call') or msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error("No function_call de búsqueda: %s", resp)
        return "Perdón, no entendí qué producto querés pedir."

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants_info = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # 3) Segundo llamado: LLM elige variante y qty
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

    # Fallback: si no hay function_call, devolvemos el contenido al usuario
    if not follow_msg.get('function_call'):
        content = follow_msg.get('content', '').strip()
        # extraer cantidad y id de variants_info[0] si es proposición de stock
        if content and '¿Te gustaría' in content:
            # asumimos primer variante
            variant = variants_info[0]
            qty = variant['stock']
            PENDING_CONFIRMATIONS[partner.id] = { 'product_id': variant['id'], 'quantity': qty }
            return content
        _logger.error("No function_call ni contenido procesable: %s", followup)
        return content or "No entendí qué variante elegiste. ¿Podés indicar el producto y cantidad?"

    # 4) Si viene llamada a create_sale_order directamente
    fn2 = follow_msg['function_call']
    args2 = json.loads(fn2['arguments'])
    product_id = args2.get('product_id')
    requested_qty = args2.get('quantity')

    # Validar vs stock
    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0
    if requested_qty > available:
        # propuesta de stock máximo
        PENDING_CONFIRMATIONS[partner.id] = { 'product_id': product_id, 'quantity': available }
        return f"Lo siento, sólo hay {available} unidades de '{variant.display_name}'. ¿Querés pedir esa cantidad en su lugar?"

    # Crear pedido
    order = create_sale_order(env, partner.id, product_id, requested_qty)
    return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."
