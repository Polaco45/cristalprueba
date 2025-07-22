/** @odoo-module **/

import { ThreadView } from "@mail/views/thread_view/thread_view";
import { patch } from "@web/core/utils/patch";

// Usamos 'patch' para añadir funcionalidad al componente original de Odoo
patch(ThreadView.prototype, 'chatbot_whatsapp.ThreadView', {

    /**
     * Esta es la función que se llama desde el t-on-click en el XML.
     * Tienes acceso a toda la información del chat a través de 'this.thread'.
     */
    onClickCustomButton() {
        alert("¡Botón del Chatbot presionado!");
        
        // Ejemplo: puedes acceder al ID del hilo (channel) actual
        const threadId = this.thread.id;
        console.log(`El ID de este hilo de WhatsApp es: ${threadId}`);
        
        // Aquí pondrías la lógica de tu chatbot...
        // Por ejemplo, llamar a un método del servidor con el ID del hilo.
    },

});