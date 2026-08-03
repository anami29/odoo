/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class CalibrationDashboard extends Component {
    static template = "custom_instrument_calibration.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            data: null,
            loading: true,
            filters: {
                period: false,
                category_id: false,
                department_id: false,
                agency_id: false,
            },
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "calibration.dashboard", "get_data", [this.state.filters]);
        this.state.loading = false;
    }

    onFilterChange(key, ev) {
        const val = ev.target.value;
        this.state.filters[key] =
            key === "period" ? (val || false) : (val ? parseInt(val) : false);
        this.load();
    }

    open(domainKey) {
        const d = this.state.data && this.state.data.domains[domainKey];
        if (!d) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: d.name,
            res_model: d.model,
            views: [[false, "list"], [false, "form"]],
            domain: d.domain,
            target: "current",
            context: { active_test: false },
        });
    }

    max(series, key = "value") {
        return Math.max(1, ...series.map((s) => s[key] || 0));
    }

    barStyle(value, max, color) {
        const pct = Math.max(2, Math.round((value / max) * 100));
        return `width:${pct}%;background:${color};`;
    }
}

registry.category("actions").add("calibration_dashboard", CalibrationDashboard);
