/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched, useRef } from "@odoo/owl";

// 1. Guardamos una referencia a la función setup original antes de modificarla.
const originalSetup = FormController.prototype.setup;

patch(FormController.prototype, {
    setup() {
        // 2. Ejecutamos la función setup original. Esto es crucial.
        originalSetup.apply(this, arguments);

        // 3. Ahora que Odoo ha inicializado todo, añadimos nuestra lógica de forma segura.
        this.chatbotContainer = useRef("chatbot_toggle_container");
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    async _renderChatbotButton() {
        if (!this.model.root || !this.model.root.data) {
             return;
        }

        const container = this.chatbotContainer.el;

        if (!container || this.model.root.resModel !== 'discuss.channel' || this.model.root.data.channel_type !== 'whatsapp') {
            if (container) {
                container.innerHTML = "";
            }
            return;
        }

        const channelId = this.model.root.resId;
        if (!channelId) {
            container.innerHTML = "";
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        // Usamos this.env.services.rpc que ya está disponible gracias al setup original.
        const result = await this.env.services.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        });

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
    },

    _onToggleChatbotClick(wasPaused, channelId) {
        const container = this.chatbotContainer.el;
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        this.env.services.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        });
    },
});