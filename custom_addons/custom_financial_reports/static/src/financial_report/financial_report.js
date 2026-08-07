/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/currency";
import { Component, onWillStart, useState } from "@odoo/owl";

export class FinancialReportView extends Component {
    static template = "custom_financial_reports.ReportView";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        const ctx = (this.props.action && this.props.action.context) || {};
        this.state = useState({
            loading: true,
            report_type: ctx.report_type || "bs",
            date_from: "",
            date_to: "",
            target_move: "posted",
            comparison: "none",
            title: "",
            company_name: "",
            lines: [],
            periods: [],
            has_comparison: false,
            currency: null,
            drill: null,
            folded: {},
        });
        onWillStart(() => this.load());
    }

    options() {
        return {
            report_type: this.state.report_type,
            date_from: this.state.date_from || false,
            date_to: this.state.date_to || false,
            target_move: this.state.target_move,
            comparison: this.state.comparison,
            detail_level: "detail",
        };
    }

    async load() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "custom.financial.report", "compute_report", [this.options()]
            );
            const o = res.options;
            this.state.report_type = o.report_type;
            this.state.date_from = o.date_from || "";
            this.state.date_to = o.date_to || "";
            this.state.target_move = o.target_move;
            this.state.comparison = o.comparison;
            const d = res.data;
            this.state.title = d.title;
            this.state.company_name = d.company_name;
            this.state.lines = d.lines;
            this.state.periods = d.periods;
            this.state.has_comparison = d.has_comparison;
            this.state.currency = d.currency;
            this.state.drill = d.drill;
            const folded = {};
            for (const line of d.lines) {
                if (line.unfoldable) {
                    folded[line.key] = this.state.folded[line.key] ?? true;
                }
            }
            this.state.folded = folded;
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) || String(error),
                { type: "danger" }
            );
        }
        this.state.loading = false;
    }

    get visibleLines() {
        return this.state.lines.filter(
            (line) => !(line.parent_key && this.state.folded[line.parent_key])
        );
    }

    get allFolded() {
        return Object.values(this.state.folded).every(Boolean);
    }

    fmt(value) {
        if (value === null || value === undefined) {
            return "";
        }
        const cur = this.state.currency;
        try {
            return formatCurrency(value, cur.id);
        } catch {
            const num = value.toLocaleString(undefined, {
                minimumFractionDigits: cur ? cur.decimal_places : 2,
                maximumFractionDigits: cur ? cur.decimal_places : 2,
            });
            if (!cur) {
                return num;
            }
            return cur.position === "before"
                ? `${cur.symbol}\u00A0${num}`
                : `${num}\u00A0${cur.symbol}`;
        }
    }

    toggleFold(line) {
        if (line.unfoldable) {
            this.state.folded[line.key] = !this.state.folded[line.key];
        }
    }

    toggleAll() {
        const target = !this.allFolded;
        for (const key of Object.keys(this.state.folded)) {
            this.state.folded[key] = target;
        }
    }

    openJournalItems(line) {
        if (!line.clickable) {
            return;
        }
        const drill = this.state.drill;
        const domain = [
            ["account_id", "=", line.account_id],
            ["parent_state", "in", drill.states],
            ["display_type", "not in", ["line_section", "line_note"]],
            ["date", "<=", drill.date_to],
        ];
        if (drill.date_from) {
            domain.push(["date", ">=", drill.date_from]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: line.name,
            res_model: "account.move.line",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
            context: { create: false },
        });
    }

    async printPdf() {
        const act = await this.orm.call(
            "custom.financial.report", "get_pdf_action", [this.options()]
        );
        this.action.doAction(act);
    }

    exportXlsx() {
        const params = new URLSearchParams();
        const opts = this.options();
        for (const [key, value] of Object.entries(opts)) {
            if (value) {
                params.set(key, value);
            }
        }
        const link = document.createElement("a");
        link.href = "/custom_financial_reports/xlsx?" + params.toString();
        link.click();
    }
}

registry.category("actions").add(
    "custom_financial_reports.report_view", FinancialReportView
);
