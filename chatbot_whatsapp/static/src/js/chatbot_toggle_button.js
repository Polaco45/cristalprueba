/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ThreadContainer } from "@mail/core/common/thread_container"; // Importación correcta para Odoo 18
import { onMounted, onPatched, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(ThreadContainer.prototype, {
    setup() {
        super.setup(...arguments);
        this.rpc = useService("rpc");
        this.state = useState({
            chatbotStatus: "unknown",
            isLoading: true,
        });

        // Hooks para asegurar que el botón se renderice y actualice correctamente
        onMounted(() => this._fetchChatbotStatus());
        onPatched(() => this._fetchChatbotStatus());
        onWillUpdateProps(async (nextProps) => {
            // Si cambiamos de canal, volvemos a buscar el estado
            if (this.props.thread?.id !== nextProps.thread?.id) {
                await this._fetchChatbotStatus(nextProps);
            }
        });
    },

    // Nueva función para saber si debemos mostrar el botón
    shouldShowChatbotButton() {
        return this.props.thread?.type === 'channel' && this.props.thread?.id;
    },

    // Función para obtener el estado del bot
    async _fetchChatbotStatus(props) {
        const thread = props ? props.thread : this.props.thread;
        if (!thread || thread.type !== 'channel' || !thread.id) {
            this.state.chatbotStatus = "unknown";
            return;
        }

        this.state.isLoading = true;
        try {
            const result = await this.rpc({
                model: 'discuss.channel',
                method: 'get_chatbot_status',
                args: [thread.id],
            });
            this.state.chatbotStatus = result.status;
        } catch (error) {
            console.error("Chatbot: Error fetching status.", error);
            this.state.chatbotStatus = "error";
        } finally {
            this.state.isLoading = false;
        }
    },

    // Función para manejar el clic en el botón
    async _onToggleChatbotClick() {
        if (!this.props.thread || !this.props.thread.id) return;

        this.state.isLoading = true;
        const wasPaused = this.state.chatbotStatus === 'paused';
        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        try {
            await this.rpc({
                model: 'discuss.channel',
                method: methodToCall,
                args: [this.props.thread.id],
            });
            // Refrescamos el estado después de la acción
            await this._fetchChatbotStatus();
        } catch (error) {
            console.error("Chatbot: Error toggling status.", error);
            this.state.chatbotStatus = "error";
            this.state.isLoading = false;
        }
    },
});