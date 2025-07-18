/** @odoo-module */

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {

    setup() {
        this._super(...arguments);
        this.rpc = useService("rpc");
    },

    async _update() {
        await this._super(...arguments);

        if (this.modelName !== 'discuss.channel' || !this.renderer.state?.data?.channel_type || this.renderer.state.data.channel_type !== 'whatsapp') {
            return;
        }

        const $container = this.el.querySelector('#chatbot_toggle_container');
        if (!$container) return;

        this.channelId = this.renderer.state.res_id;
        this.renderChatbotButton($container);
    },

    renderChatbotButton(container) {
        container.innerHTML = '';

        this.rpc
            .query({
                model: 'discuss.channel',
                method: 'get_chatbot_status',
                args: [this.channelId],
            })
            .then(result => {
                const isPaused = result.status === 'paused';
                const buttonText = isPaused ? 'Reanudar Chatbot' : 'Pausar Chatbot';
                const buttonIcon = isPaused ? 'fa-play' : 'fa-pause';
                const buttonClass = isPaused ? 'btn-success' : 'btn-warning';

                const button = document.createElement('button');
                button.className = `btn ${buttonClass} btn-sm`;
                button.innerHTML = `<i class="fa ${buttonIcon}"></i> ${buttonText}`;
                button.addEventListener('click', () => {
                    this._onToggleChatbotClick(isPaused, container);
                });

                container.appendChild(button);
            });
    },

    _onToggleChatbotClick(wasPaused, container) {
        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';
        container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';

        this.rpc
            .query({
                model: 'discuss.channel',
                method: methodToCall,
                args: [this.channelId],
            })
            .then(() => {
                this.renderChatbotButton(container);
            });
    },
});
