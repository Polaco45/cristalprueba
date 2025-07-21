/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

// 1. Definimos nuestro nuevo Componente de OWL para el ícono
class ChatbotSystrayIcon extends Component {
    static template = "chatbot_whatsapp.ChatbotSystrayIcon"; // Apunta al XML que crearemos

    _onClick() {
        // Por ahora, una simple alerta para confirmar que funciona
        alert("¡Hola Mundo! El componente funciona.");
    }
}

// 2. Registramos nuestro componente en la categoría "systray" de Odoo
// Odoo sabe que todo lo que está en esta categoría va en la barra superior
registry.category("systray").add("chatbot_whatsapp.systray_icon", {
    Component: ChatbotSystrayIcon,
    sequence: 1, // 'sequence' bajo para que aparezca primero (a la izquierda)
});