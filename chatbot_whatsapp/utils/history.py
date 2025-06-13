# utils/history.py

from datetime import datetime, timedelta

def get_recent_history(env, partner, limit=6):
    messages = env['chatbot.history'].sudo().search([
        ('partner_id', '=', partner.id)
    ], order='id desc', limit=limit)
    return [
        _format_entry(msg)
        for msg in reversed(messages)
    ]

def save_message(env, partner, role, message, function_name=None):
    env['chatbot.history'].sudo().create({
        'partner_id': partner.id,
        'role': role,
        'message': message,
        'function_name': function_name,
    })

def _format_entry(msg):
    entry = {"role": msg.role, "content": msg.message}
    if msg.role == "function" and msg.function_name:
        entry["name"] = msg.function_name
    return entry
