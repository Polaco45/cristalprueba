/** @odoo-module */

import { patch } from "@web/core/utils/patch";
// 🎯 ¡Importante! Importamos el componente correcto: ThreadHeader
import { ThreadHeader } from "@mail/core/common/thread_header"; 
import { onMounted, onPatched } from "@odoo/owl";

// Guardamos el setup original del componente que vamos a parchear
const originalSetup = ThreadHeader.prototype.setup;
    
patch(ThreadHeader.prototype, {
    setup() {
        // Llamamos al setup original primero
        originalSetup.apply(this, arguments);

        // Los hooks onMounted y onPatched aseguran que nuestro botón se renderice
        // al cargar y al actualizar el componente.
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    async _renderChatbotButton() {
        // Buscamos el contenedor DENTRO del elemento de este componente (this.el)
        const container = this.el.querySelector('#chatbot_toggle_container');

        // Si no encontramos el contenedor o el chat no es un canal, no hacemos nada.
        if (!container || this.props.thread?.type !== 'channel') {
            if (container) container.innerHTML = ""; // Limpiamos por si acaso
            return;
        }

        const channelId = this.props.thread.id;
        if (!channelId) {
            container.innerHTML = "";
            return;
        }

        // Muestra un spinner mientras carga
        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        // Hacemos la llamada RPC para saber el estado del chatbot
        const result = await this.env.services.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        });
        
        // Es posible que el contenedor ya no exista si el usuario navegó rápido
        const currentContainer = this.el.querySelector('#chatbot_toggle_container');
        if (!currentContainer) return;

        // Construimos el botón basado en la respuesta
        const isPaused = result.status === 'paused';
        const button = document.createElement("button");
        button.className = `btn btn-sm ${isPaused ? "btn-success" : "btn-warning"}`;
        button.innerHTML = `<i class="fa ${isPaused ? "fa-play" : "fa-pause"} me-1"></i> ${isPaused ? "Reanudar Chatbot" : "Pausar Chatbot"}`;

        button.addEventListener("click", () => {
            this._onToggleChatbotClick(isPaused, channelId);
        });
        
        currentContainer.innerHTML = "";
        currentContainer.appendChild(button);
    },

    // La lógica para el clic es la misma que ya tenías
    _onToggleChatbotClick(wasPaused, channelId) {
        const container = this.el.querySelector('#chatbot_toggle_container');
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        this.env.services.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        }).then(() => {
            // Forzamos una actualización para que el botón se vuelva a renderizar
            // con el nuevo estado.
            this._renderChatbotButton();
        });
    },
});