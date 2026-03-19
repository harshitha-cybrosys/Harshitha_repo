/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

export class InvoiceOcrListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
    }

    async onClickOcrInvoice() {
        const context = this.props.context || {};
        const activeModel = this.props.resModel;
        const moveType = context.default_move_type || null;
        try {
            const result = await this.orm.call(
                "account.move",
                "check_active_boolean_invoice",
                [activeModel, moveType],
            );
            if (result.active) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    res_model: "import.via.ocr",
                    name: "Import via OCR",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        active_model: activeModel,
                        record_id: result.record_id,
                        default_move_type: moveType,
                    },
                });
            } else {
                this.notification.add(
                    "No active OCR configuration found. Go to Settings → OCR AI Integration.",
                    { type: "danger" }
                );
            }
        } catch (error) {
            this.notification.add("OCR error: " + error.message, { type: "danger" });
        }
    }
}

registry.category("views").add("ocr_button_invoice", {
    ...listView,
    Controller: InvoiceOcrListController,
    buttonTemplate: "ocr_ai_invoice.ListView.Buttons",
});