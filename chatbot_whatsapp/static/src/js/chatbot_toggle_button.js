/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, useRef } from "@odoo/owl";

// 👇 CORRECCIÓN AQUÍ: Eliminamos el segundo argumento "chatbot_whatsapp.FormControllerPatch"
patch(FormController.prototype, {
    setup() {
        this._super(...arguments); 
        this.rpc = useService("rpc");
        this.chatbotContainer = useRef("chatbot_toggle_container");

        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    _renderChatbotButton() {
        if (!this.model.root || !this.model.root.data) {
             return;
        }

        if (this.model.root.resModel !== 'discuss.channel' ||
            this.model.root.data.channel_type !== 'whatsapp') {
            // Si el contenedor existe, lo vaciamos para que no queden botones viejos
            if (this.chatbotContainer.el) {
                this.chatbotContainer.el.innerHTML = "";
            }
            return;
        }

        const container = this.chatbotContainer.el;
        if (!container) {
            return; 
        }
        
        const channelId = this.model.root.resId;
        if (!channelId) {
            container.innerHTML = "";
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        this.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        }).then(result => {
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
        // onPatched se encargará de volver a renderizar automáticamente
    },
});