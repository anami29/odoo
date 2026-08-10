/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/currency";
import {
    Component, onWillStart, useState, useExternalListener,
} from "@odoo/owl";

function iso(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function fromIso(s) {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);
}

function endOfMonth(d) {
    return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function shiftYears(s, n) {
    const d = fromIso(s);
    d.setFullYear(d.getFullYear() + n);
    return iso(d);
}

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
            openMenu: null,
            report_type: ctx.report_type || "bs",
            date_from: "",
            date_to: "",
            target_move: "posted",
            comparison: "none",
            periods_count: 1,
            comparison_date: "",
            journal_ids: [],
            hide_zero: false,
            title: "",
            company_name: "",
            lines: [],
            periods: [],
            currency: null,
            fy: null,
            has_unposted: false,
            drill: null,
            folded: {},
            journals: [],
        });
        useExternalListener(window, "click", () => {
            this.state.openMenu = null;
        });
        onWillStart(async () => {
            this.state.journals = await this.orm.searchRead(
                "account.journal", [], ["name", "code", "type"]
            );
            await this.load();
        });
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------
    options() {
        return {
            report_type: this.state.report_type,
            date_from: this.state.date_from || false,
            date_to: this.state.date_to || false,
            target_move: this.state.target_move,
            comparison: this.state.comparison,
            periods_count: this.state.periods_count,
            comparison_date: this.state.comparison_date || false,
            journal_ids: [...this.state.journal_ids],
            detail_level: "detail",
            hide_zero: this.state.hide_zero,
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
            this.state.periods_count = o.periods_count;
            this.state.comparison_date = o.comparison_date || "";
            this.state.journal_ids = o.journal_ids || [];
            this.state.hide_zero = o.hide_zero;
            const d = res.data;
            this.state.title = d.title;
            this.state.company_name = d.company_name;
            this.state.lines = d.lines;
            this.state.periods = d.periods;
            this.state.currency = d.currency;
            this.state.fy = d.fy;
            this.state.has_unposted = d.has_unposted;
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

    // ------------------------------------------------------------------
    // Header helpers
    // ------------------------------------------------------------------
    toggleMenu(name, ev) {
        ev.stopPropagation();
        this.state.openMenu = this.state.openMenu === name ? null : name;
    }

    get dateLabel() {
        return this.state.periods[0] ? this.state.periods[0].label : "";
    }

    get comparisonLabel() {
        const map = {
            none: "Comparison",
            previous_period: `Previous Period (${this.state.periods_count})`,
            same_last_year: `Same Period Last Year (${this.state.periods_count})`,
            specific_date: "Specific Date",
        };
        return map[this.state.comparison];
    }

    get journalsLabel() {
        const n = this.state.journal_ids.length;
        if (!n) {
            return "All Journals";
        }
        if (n === 1) {
            const j = this.state.journals.find(
                (j) => j.id === this.state.journal_ids[0]
            );
            return j ? j.name : "1 Journal";
        }
        return `${n} Journals`;
    }

    get optionsLabel() {
        return this.state.target_move === "posted"
            ? "Posted Entries"
            : "Draft Entries Included";
    }

    get currencyLabel() {
        const c = this.state.currency;
        return c ? `In ${c.symbol || c.name}` : "";
    }

    get datePresets() {
        const today = new Date();
        if (this.state.report_type === "bs") {
            const lastMonth = endOfMonth(
                new Date(today.getFullYear(), today.getMonth() - 1, 1));
            const qStart = new Date(
                today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);
            const lastQuarter = new Date(qStart - 86400000);
            const presets = [
                { name: "Today", date_to: iso(today) },
                { name: "End of Last Month", date_to: iso(lastMonth) },
                { name: "End of Last Quarter", date_to: iso(lastQuarter) },
            ];
            if (this.state.fy) {
                presets.push({
                    name: "End of Last Financial Year",
                    date_to: iso(new Date(
                        fromIso(this.state.fy.date_from) - 86400000)),
                });
            }
            return presets;
        }
        const y = today.getFullYear();
        const m = today.getMonth();
        const q = Math.floor(m / 3) * 3;
        const presets = [
            { name: "This Month",
              date_from: iso(new Date(y, m, 1)),
              date_to: iso(endOfMonth(today)) },
            { name: "Last Month",
              date_from: iso(new Date(y, m - 1, 1)),
              date_to: iso(new Date(y, m, 0)) },
            { name: "This Quarter",
              date_from: iso(new Date(y, q, 1)),
              date_to: iso(new Date(y, q + 3, 0)) },
            { name: "Last Quarter",
              date_from: iso(new Date(y, q - 3, 1)),
              date_to: iso(new Date(y, q, 0)) },
        ];
        if (this.state.fy) {
            presets.push({
                name: "This Financial Year",
                date_from: this.state.fy.date_from,
                date_to: this.state.fy.date_to,
            });
            presets.push({
                name: "Last Financial Year",
                date_from: shiftYears(this.state.fy.date_from, -1),
                date_to: iso(new Date(
                    fromIso(this.state.fy.date_from) - 86400000)),
            });
        }
        return presets;
    }

    applyPreset(preset) {
        if (preset.date_from) {
            this.state.date_from = preset.date_from;
        }
        this.state.date_to = preset.date_to;
        this.state.openMenu = null;
        this.load();
    }

    setComparison(mode) {
        this.state.comparison = mode;
        if (mode === "specific_date" && !this.state.comparison_date) {
            this.state.comparison_date = shiftYears(this.state.date_to, -1);
        }
        this.load();
    }

    toggleJournal(id) {
        const idx = this.state.journal_ids.indexOf(id);
        if (idx >= 0) {
            this.state.journal_ids.splice(idx, 1);
        } else {
            this.state.journal_ids.push(id);
        }
        this.load();
    }

    clearJournals() {
        this.state.journal_ids = [];
        this.load();
    }

    toggleDraft() {
        this.state.target_move =
            this.state.target_move === "posted" ? "all" : "posted";
        this.load();
    }

    toggleHideZero() {
        this.state.hide_zero = !this.state.hide_zero;
        this.load();
    }

    setFoldAll(folded) {
        for (const key of Object.keys(this.state.folded)) {
            this.state.folded[key] = folded;
        }
        this.state.openMenu = null;
    }

    // ------------------------------------------------------------------
    // Table
    // ------------------------------------------------------------------
    get visibleLines() {
        return this.state.lines.filter(
            (line) => !(line.parent_key && this.state.folded[line.parent_key])
        );
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
        if (drill.journal_ids && drill.journal_ids.length) {
            domain.push(["journal_id", "in", drill.journal_ids]);
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

    openDraftEntries() {
        const domain = [
            ["state", "=", "draft"],
            ["date", "<=", this.state.date_to],
        ];
        if (this.state.journal_ids.length) {
            domain.push(["journal_id", "in", this.state.journal_ids]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Unposted Journal Entries",
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // Exports
    // ------------------------------------------------------------------
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
            if (Array.isArray(value)) {
                if (value.length) {
                    params.set(key, value.join(","));
                }
            } else if (value) {
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
