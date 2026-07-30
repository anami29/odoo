/** @odoo-module **/

import { Component, useState, onWillStart, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";

export class ZSalesPurchaseDashboard extends Component {
    static template = "custom_sales_purchase_dashboard.ZSalesPurchaseDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Refs for canvas elements
        this.trendCanvasRef = useRef("trendCanvas");
        this.rateCanvasRef = useRef("rateCanvas");
        this.partnerCanvasRef = useRef("partnerCanvas");

        // Charts instances
        this.trendChart = null;
        this.rateChart = null;
        this.partnerChart = null;

        // Current Date Presets
        const today = new Date();
        const curYear = today.getFullYear();
        const curMonth = today.getMonth() + 1; // 1-indexed

        // Default Fiscal Year label (e.g. 2026-27)
        let defaultFY = `${curYear}-${String(curYear + 1).slice(-2)}`;
        if (curMonth < 4) { // Before April, we are in previous fiscal year
            defaultFY = `${curYear - 1}-${String(curYear).slice(-2)}`;
        }

        // Initialize state
        this.state = useState({
            type: "sales", // 'sales' or 'purchase'
            basis: "accounting", // 'accounting' or 'invoice'/'bill'
            periodMode: "month", // 'month', 'quarter', 'year', 'custom'
            fiscalYear: defaultFY,
            month: String(curMonth),
            quarter: "q1",
            dateFrom: "",
            dateTo: "",
            search: "",
            limit: 10,
            offset: 0,
            currentPage: 1,
            totalCount: 0,
            records: [],
            kpis: {},
            graphs: {},
            wizardsInstalled: { sales: false, purchase: false }
        });

        // Generate months and fiscal years for dropdowns
        this.months = [
            { value: "1", label: _t("January") }, { value: "2", label: _t("February") },
            { value: "3", label: _t("March") }, { value: "4", label: _t("April") },
            { value: "5", label: _t("May") }, { value: "6", label: _t("June") },
            { value: "7", label: _t("July") }, { value: "8", label: _t("August") },
            { value: "9", label: _t("September") }, { value: "10", label: _t("October") },
            { value: "11", label: _t("November") }, { value: "12", label: _t("December") }
        ];

        this.fiscalYears = [];
        for (let y = curYear - 2; y <= curYear + 1; y++) {
            this.fiscalYears.push({
                value: `${y}-${String(y + 1).slice(-2)}`,
                label: `FY ${y}-${String(y + 1).slice(-2)}`
            });
        }

        this.quarters = [
            { value: "q1", label: _t("Q1 (Apr - Jun)") },
            { value: "q2", label: _t("Q2 (Jul - Sep)") },
            { value: "q3", label: _t("Q3 (Oct - Dec)") },
            { value: "q4", label: _t("Q4 (Jan - Mar)") }
        ];

        // Resolve dates on start
        this.resolveDates();

        // Life cycle hooks
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            const wStatus = await this.orm.call(
                "custom.sales.purchase.dashboard",
                "check_wizard_availability",
                []
            );
            this.state.wizardsInstalled = wStatus;
            await this.loadDashboardData();
        });

        useEffect(() => {
            this.renderCharts();
            return () => this.destroyCharts();
        }, () => [this.state.graphs]);
    }

    resolveDates() {
        if (this.state.periodMode === "custom") return;

        const fyStartYear = parseInt(this.state.fiscalYear.split("-")[0]);
        let startYear = fyStartYear;
        let endYear = fyStartYear;
        let startMonth = 4; // April (standard Indian fiscal year start)
        
        if (this.state.periodMode === "year") {
            this.state.dateFrom = `${fyStartYear}-04-01`;
            this.state.dateTo = `${fyStartYear + 1}-03-31`;
        } else if (this.state.periodMode === "quarter") {
            const q = this.state.quarter;
            if (q === "q1") {
                this.state.dateFrom = `${fyStartYear}-04-01`;
                this.state.dateTo = `${fyStartYear}-06-30`;
            } else if (q === "q2") {
                this.state.dateFrom = `${fyStartYear}-07-01`;
                this.state.dateTo = `${fyStartYear}-09-30`;
            } else if (q === "q3") {
                this.state.dateFrom = `${fyStartYear}-10-01`;
                this.state.dateTo = `${fyStartYear}-12-31`;
            } else if (q === "q4") {
                this.state.dateFrom = `${fyStartYear + 1}-01-01`;
                this.state.dateTo = `${fyStartYear + 1}-03-31`;
            }
        } else if (this.state.periodMode === "month") {
            const m = parseInt(this.state.month);
            const calYear = m < 4 ? fyStartYear + 1 : fyStartYear;
            const lastDay = new Date(calYear, m, 0).getDate();
            const padMonth = String(m).padStart(2, "0");
            this.state.dateFrom = `${calYear}-${padMonth}-01`;
            this.state.dateTo = `${calYear}-${padMonth}-${lastDay}`;
        }
    }

    async loadDashboardData() {
        const params = {
            type: this.state.type,
            basis: this.state.basis,
            date_from: this.state.dateFrom,
            date_to: this.state.dateTo,
            limit: this.state.limit,
            offset: this.state.offset,
            search: this.state.search
        };

        try {
            const res = await this.orm.call(
                "custom.sales.purchase.dashboard",
                "retrieve_dashboard_data",
                [params]
            );
            this.state.kpis = res.kpis || {};
            this.state.graphs = res.graphs || {};
            this.state.records = res.table.records || [];
            this.state.totalCount = res.table.total_count || 0;
        } catch (error) {
            console.error("Dashboard error:", error);
            this.notification.add(_t("Error loading dashboard data"), { type: "danger" });
        }
    }

    async onFilterChange() {
        this.resolveDates();
        this.state.offset = 0;
        this.state.currentPage = 1;
        await this.loadDashboardData();
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.offset = 0;
        this.state.currentPage = 1;
        await this.loadDashboardData();
    }

    async setType(type) {
        this.state.type = type;
        this.state.basis = type === "sales" ? "accounting" : "accounting";
        this.state.offset = 0;
        this.state.currentPage = 1;
        await this.loadDashboardData();
    }

    async setPage(page) {
        const maxPage = Math.ceil(this.state.totalCount / this.state.limit) || 1;
        if (page < 1 || page > maxPage) return;
        this.state.currentPage = page;
        this.state.offset = (page - 1) * this.state.limit;
        await this.loadDashboardData();
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 2
        }).format(amount || 0);
    }

    destroyCharts() {
        if (this.trendChart) this.trendChart.destroy();
        if (this.rateChart) this.rateChart.destroy();
        if (this.partnerChart) this.partnerChart.destroy();
    }

    renderCharts() {
        this.destroyCharts();

        const graphs = this.state.graphs;
        if (!graphs || !graphs.monthly_trend) return;

        // Chart 1: Monthly Trend (Line / Bar)
        if (this.trendCanvasRef.el) {
            const ctx = this.trendCanvasRef.el.getContext("2d");
            this.trendChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: graphs.monthly_trend.labels,
                    datasets: [{
                        label: this.state.type === "sales" ? _t("Net Sales Subtotal") : _t("Net Purchase Subtotal"),
                        data: graphs.monthly_trend.data,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.1)",
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            ticks: {
                                callback: (val) => this.formatCurrency(val)
                            }
                        }
                    }
                }
            });
        }

        // Chart 2: GST Rate Distribution (Pie / Doughnut)
        if (this.rateCanvasRef.el) {
            const ctx = this.rateCanvasRef.el.getContext("2d");
            this.rateChart = new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: graphs.gst_rate_dist.labels,
                    datasets: [{
                        data: graphs.gst_rate_dist.data,
                        backgroundColor: [
                            "#3b82f6", "#10b981", "#06b6d4", "#f59e0b", "#ef4444", "#8b5cf6"
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: { boxWidth: 12, font: { size: 11 } }
                        }
                    }
                }
            });
        }

        // Chart 3: Top Customers / Vendors (Pie Chart)
        if (this.partnerCanvasRef.el) {
            const ctx = this.partnerCanvasRef.el.getContext("2d");
            this.partnerChart = new Chart(ctx, {
                type: "pie",
                data: {
                    labels: graphs.partner_dist.labels,
                    datasets: [{
                        data: graphs.partner_dist.data,
                        backgroundColor: [
                            "#06b6d4", "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#64748b"
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: { boxWidth: 12, font: { size: 11 } }
                        }
                    }
                }
            });
        }
    }

    async onExportExcel() {
        const params = {
            type: this.state.type,
            basis: this.state.basis,
            date_from: this.state.dateFrom,
            date_to: this.state.dateTo
        };

        this.notification.add(_t("Exporting register to Excel..."), { type: "info" });
        
        try {
            const action = await this.orm.call(
                "custom.sales.purchase.dashboard",
                "trigger_excel_export",
                [params]
            );

            if (action.warning) {
                this.notification.add(action.warning, { type: "warning" });
            } else {
                this.action.doAction(action);
                this.notification.add(_t("Report exported successfully"), { type: "success" });
            }
        } catch (error) {
            console.error("Export error:", error);
            this.notification.add(_t("Error generating Excel report"), { type: "danger" });
        }
    }
}

// Register as Client Action
registry.category("actions").add("sales_purchase_dashboard", ZSalesPurchaseDashboard);
