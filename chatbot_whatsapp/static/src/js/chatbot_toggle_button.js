/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, useRef } from "@odoo/owl";

patch(FormController.prototype, "chatbot_whatsapp.FormControllerPatch", {
    setup() {
        this._super(...arguments); // ✅ Forma correcta de llamar al setup original
        this.rpc = useService("rpc");
        this.chatbotContainer = useRef("chatbot_toggle_container");

        // Usamos los "hooks" del ciclo de vida de Owl para renderizar el botón
        // Esto asegura que el HTML exista antes de intentar modificarlo.
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    _renderChatbotButton() {
        // Condición para asegurarnos de que estamos en el lugar correcto
        if (this.model.root.resModel !== 'discuss.channel' ||
            !this.model.root.data ||
            this.model.root.data.channel_type !== 'whatsapp') {
            return;
        }

        const container = this.chatbotContainer.el;
        if (!container) {
            return; // El contenedor aún no está en el DOM, esperamos al siguiente ciclo
        }
        
        const channelId = this.model.root.resId;
        if (!channelId) {
            container.innerHTML = ""; // Limpiamos si es un registro nuevo sin guardar
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>'; // Indicador de carga

        this.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        }).then(result => {
            if (!this.chatbotContainer.el) return; // El componente podría haberse desmontado

            const isPaused = result.status === 'paused';
            const button = document.createElement("button");
            button.className = `btn btn-sm ${isPaused ? "btn-success" : "btn-warning"}`;
            button.innerHTML = `<i class="fa ${isPaused ? "fa-play" : "fa-pause"} me-1"></i> ${isPaused ? "Reanudar Chatbot" : "Pausar Chatbot"}`;

            button.addEventListener("click", () => {
                this._onToggleChatbotClick(isPaused, channelId);
            });
            
            this.chatbotContainer.el.innerHTML = ""; // Limpiamos el spinner
            this.chatbotContainer.el.appendChild(button);
        });
    },

    _onToggleChatbotClick(wasPaused, channelId) {
        const container = this.chatbotContainer.el;
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        this.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        }).then(() => {
            // No es necesario llamar a renderizar de nuevo, onPatched lo hará automáticamente
        });
    },
});