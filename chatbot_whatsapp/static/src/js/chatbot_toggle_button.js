/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onPatched, onMounted, useRef } from "@odoo/owl";

patch(FormController.prototype, "chatbot_whatsapp.ChatbotToggleButtonPatch", {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
        this.chatbotContainer = useRef("chatbot_toggle_container");

        onMounted(() => this.renderChatbotButton());
        onPatched(() => this.renderChatbotButton());
    },

    renderChatbotButton() {
        if (this.model.root.resModel !== 'discuss.channel' ||
            this.model.root.data.channel_type !== 'whatsapp') {
            return;
        }

        const container = this.chatbotContainer.el;
        if (!container) {
            return;
        }

        // Limpiamos el contenedor para evitar botones duplicados
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }

        const channelId = this.model.root.resId;
        if (!channelId) {
            return; // No hacer nada si es un registro nuevo sin guardar
        }

        this.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        }).then(result => {
            const isPaused = result.status === 'paused';
            const buttonText = isPaused ? 'Reanudar Chatbot' : 'Pausar Chatbot';
            const buttonIcon = isPaused ? 'fa-play' : 'fa-pause';
            const buttonClass = isPaused ? 'btn-success' : 'btn-warning';

            const button = document.createElement('button');
            button.className = `btn ${buttonClass} btn-sm`;
            button.innerHTML = `<i class="fa ${buttonIcon} me-1"/>${buttonText}`;

            button.addEventListener('click', () => {
                this._onToggleChatbotClick(isPaused, channelId, container);
            });

            container.appendChild(button);
        });
    },

    _onToggleChatbotClick(wasPaused, channelId, container) {
        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';
        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        this.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        }).then(() => {
            this.renderChatbotButton(); // Volvemos a renderizar el botón
        });
    },
});