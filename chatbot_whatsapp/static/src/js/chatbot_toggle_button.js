odoo.define('chatbot_whatsapp/js/chatbot_toggle_button', function (require) {
    "use strict";

    const FormController = require('web.FormController');
    const rpc = require('web.rpc');
    const { patch } = require('web.utils');

    patch(FormController.prototype, 'chatbot_whatsapp.ChatbotToggleButtonPatch', { 
        /**
         * Sobrescribimos el método _update para que se ejecute cada vez que la vista se actualiza.
         */
        _update: async function () {
            await this._super.apply(this, arguments);

            // --- LÍNEAS DE DEPURACIÓN ---
            console.log("Model:", this.modelName);
            if (this.renderer.state.data) {
                console.log("Channel Type:", this.renderer.state.data.channel_type);
            }
            // ----------------------------

            // Solo actuamos en el modelo 'discuss.channel' y si es de tipo whatsapp
            if (this.modelName !== 'discuss.channel' || !this.renderer.state.data.channel_type || this.renderer.state.data.channel_type !== 'whatsapp') {
                return;
            }

            const $container = this.$('#chatbot_toggle_container');
            if (!$container.length) {
                return;
            }

            this.channelId = this.renderer.state.res_id;
            this.renderChatbotButton($container);
        },

        /**
         * Dibuja el botón y le asigna la funcionalidad.
         * @param {jQuery} $container El div donde se insertará el botón.
         */
        renderChatbotButton: function ($container) {
            $container.empty(); // Limpiamos el contenedor

            rpc.query({
                model: 'discuss.channel',
                method: 'get_chatbot_status',
                args: [this.channelId],
            }).then(result => {
                const isPaused = result.status === 'paused';
                const buttonText = isPaused ? 'Reanudar Chatbot' : 'Pausar Chatbot';
                const buttonIcon = isPaused ? 'fa-play' : 'fa-pause';
                const buttonClass = isPaused ? 'btn-success' : 'btn-warning';

                const $button = $(`<button class="btn ${buttonClass} btn-sm"><i class="fa ${buttonIcon}"/> ${buttonText}</button>`);
                
                $button.on('click', () => {
                    this._onToggleChatbotClick(isPaused);
                });

                $container.append($button);
            });
        },

        /**
         * Maneja el evento de clic en el botón.
         * @param {boolean} wasPaused El estado del botón antes del clic.
         */
        _onToggleChatbotClick: function (wasPaused) {
            const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';
            const $container = this.$('#chatbot_toggle_container');

            // Muestra un estado de carga
            $container.html('<i class="fa fa-spinner fa-spin"/>');

            rpc.query({
                model: 'discuss.channel',
                method: methodToCall,
                args: [this.channelId],
            }).then(() => {
                // Una vez que la acción del backend termina, volvemos a dibujar el botón
                // para que muestre el nuevo estado.
                this.renderChatbotButton($container);
            });
        },
    });
});