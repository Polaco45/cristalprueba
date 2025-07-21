/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ThreadTopbar } from "@mail/components/thread_topbar/thread_topbar";
import { useService } from "@web/core/utils/hooks";

patch(ThreadTopbar.prototype, {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
    },

    // Este getter añade tu botón al array de botones que ya pinta el topbar
    get extraButtons() {
        const base = super.extraButtons || [];
        return [
            ...base,
            {
                key: "chatbot_toggle",
                icon: "fa fa-robot",
                title: "Pausar/Reanudar Chatbot",
                className: "btn btn-sm btn-secondary",
                onClick: () => this._toggleChatbot(),
            }
        ];
    },

    async _toggleChatbot() {
        const channelId = this.thread?.id;
        if (!channelId) return;
        // 1) pido estado
        const { status } = await this.rpc({
            model: "discuss.channel",
            method: "get_chatbot_status",
            args: [channelId],
        });
        // 2) decido método
        const method = status === "paused"
            ? "action_resume_chatbot"
            : "action_pause_chatbot";
        // 3) ejecuto
        await this.rpc({
            model: "discuss.channel",
            method,
            args: [channelId],
        });
        // 4) opcional: feedback
        this.env.services.notification.add(
            status === "paused"
                ? "Chatbot reanudado"
                : "Chatbot pausado",
            { type: "success" }
        );
    },
});
