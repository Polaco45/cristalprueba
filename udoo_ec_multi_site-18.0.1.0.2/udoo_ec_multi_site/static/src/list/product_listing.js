import { listView } from '@web/views/list/list_view';
import { registry } from '@web/core/registry';
import { ListController } from '@web/views/list/list_controller';

export class MultiWebsiteProductListController extends ListController {
    async onMultiUpdate() {
        let records = this.model.root.selection;
        const resIds = records.map((record) => record.data.product_id[0]);
        await this.actionService.doAction('udoo_ec_multi_site.action_multi_product_setter', {
            additionalContext: { default_product_ids: resIds, },
            onClose: async () => {
                await this.model.root.load();
                this.render(true);
            }
        });
    }
}

export const MultiWebsiteProductListView = {
    ...listView,
    Controller: MultiWebsiteProductListController,
    buttonTemplate: 'ooo.MultiWebsiteProduct.Buttons',
};

registry.category('views').add('ooo_multi_website_product', MultiWebsiteProductListView);
