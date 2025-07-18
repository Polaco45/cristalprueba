/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, useRef } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        // La utilidad "patch" se encarga de llamar al setup original.
        // Por eso, eliminamos la línea "this._super(...arguments);" que causaba el error.
        this.rpc = useService("rpc");
        this.chatbotContainer = useRef("chatbot_toggle_container");

        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    _renderChatbotButton() {
        // Verificamos que el componente no se haya destruido
        if (!this.model.root || !this.model.root.data) {
             return;
        }

        const container = this.chatbotContainer.el;

        // Si el contenedor no está o no estamos en el canal correcto, lo vaciamos y salimos.
        if (!container || this.model.root.resModel !== 'discuss.channel' || this.model.root.data.channel_type !== 'whatsapp') {
            if (container) {
                container.innerHTML = "";
            }
            return;
        }
        
        const channelId = this.model.root.resId;
        if (!channelId) {
            container.innerHTML = ""; // Limpiamos si es un registro nuevo sin guardar
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>'; // Indicador de carga

        this.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        }).then(result => {
            // Volvemos a verificar por si el usuario navegó a otro lado mientras se hacía la llamada
            if (!this.chatbotContainer.el) return;

            const isPaused = result.status === 'paused';
            const button = document.createElement("button");
            button.className = `btn btn-sm ${isPaused ? "btn-success" : "btn-warning"}`;
            button.innerHTML = `<i class="fa ${isPaused ? "fa-play" : "fa-pause"} me-1"></i> ${isPaused ? "Reanudar Chatbot" : "Pausar Chatbot"}`;

            button.addEventListener("click", () => {
                this._onToggleChatbotClick(isPaused, channelId);
            });
            
            this.chatbotContainer.el.innerHTML = "";
            this.chatbotContainer.el.appendChild(button);
        });
    },

    _onToggleChatbotClick(wasPaused, channelId) {
        const container = this.chatbotContainer.el;
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        this.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        });
        // onPatched se encargará de volver a renderizar el botón automáticamente después de la acción.
    },
});