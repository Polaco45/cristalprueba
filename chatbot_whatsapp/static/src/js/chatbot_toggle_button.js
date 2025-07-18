/** @odoo-module */

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, 'chatbot_whatsapp.ToggleButton', {

    /**
     * setup recibe el original como primer parámetro.
     */
    setup(original) {
        // llamamos al setup original
        original.call(this, ...Array.prototype.slice.call(arguments, 1));
        // luego inyectamos nuestro servicio RPC
        this.rpc = useService("rpc");
    },

    /**
     * _update recibe el original como primer parámetro.
     */
    async _update(original) {
        // llamamos al update original
        await original.call(this, ...Array.prototype.slice.call(arguments, 1));

        // solo actuamos en canal WhatsApp
        if (
            this.modelName !== 'discuss.channel' ||
            !this.renderer.state?.data?.channel_type ||
            this.renderer.state.data.channel_type !== 'whatsapp'
        ) {
            return;
        }

        const container = this.el.querySelector('#chatbot_toggle_container');
        if (!container) return;

        this.channelId = this.renderer.state.res_id;
        this._renderChatbotButton(container);
    },

    /**
     * Métodos auxiliares
     */
    _renderChatbotButton(container) {
        container.innerHTML = '';
        this.rpc.query({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [this.channelId],
        }).then(result => {
            const isPaused = result.status === 'paused';
            const buttonText = isPaused ? 'Reanudar Chatbot' : 'Pausar Chatbot';
            const buttonIcon = isPaused ? 'fa-play' : 'fa-pause';
            const buttonClass = isPaused ? 'btn-success' : 'btn-warning';

            const btn = document.createElement('button');
            btn.className = `btn ${buttonClass} btn-sm`;
            btn.innerHTML = `<i class="fa ${buttonIcon}"></i> ${buttonText}`;
            btn.addEventListener('click', () => {
                this._onToggleChatbotClick(isPaused, container);
            });
            container.appendChild(btn);
        });
    },

    _onToggleChatbotClick(wasPaused, container) {
        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';
        container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
        this.rpc.query({
            model: 'discuss.channel',
            method: methodToCall,
            args: [this.channelId],
        }).then(() => {
            this._renderChatbotButton(container);
        });
    },

});
