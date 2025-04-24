/** @odoo-module **/

import {Component, xml} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";

export class WebDraftInvoiceRibbon extends Component {
    setup() {
        this.orm = useService("orm");
        useBus(this.env.bus, "WEB_CLIENT_READY", this.showRibbon.bind(this));
    }

    async showRibbon() {
        const ribbon = $(".test-ribbon");
        ribbon.hide();

        try {
            const result = await this.orm.call("web.draft.invoice.ribbon", "get_draft_invoice_status");

            console.log("Datos del ribbon:", result);

            if (result.show_ribbon) {
                ribbon.show();
                ribbon.html(`Facturas en borrador: ${result.qty}`);
                // ribbon.css("background-color", "#D0442C");
                // ribbon.css("color", "#FFFFFF");
            }
        } catch (error) {
            console.error("Error al obtener el estado del ribbon:", error);
        }
    }
}

WebDraftInvoiceRibbon.template = xml`<div class="test-ribbon" />`;

registry.category("main_components").add("WebDraftInvoiceRibbon", {
    Component: WebDraftInvoiceRibbon,
});
