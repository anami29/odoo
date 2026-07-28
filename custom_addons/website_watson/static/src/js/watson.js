/** @odoo-module **/
/*
 * Watson Logistics — frontend behaviour.
 *
 * Registered as a public widget so it runs on every page render, including
 * after the Website Builder saves, and stays inert while editing so the
 * reveal animations never hide a block the client is trying to edit.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.WatsonSite = publicWidget.Widget.extend({
    selector: "#wrapwrap",

    start() {
        // Never animate inside the editor — hidden blocks are unselectable.
        if (document.body.classList.contains("editor_enable")) {
            this.el.querySelectorAll(".reveal").forEach((el) => el.classList.add("in"));
            return this._super(...arguments);
        }
        this._initWatson();
        return this._super(...arguments);
    },

    _initWatson() {
        const root = this.el;
        const $ = (s, c) => (c || root).querySelector(s);
        const $$ = (s, c) => Array.from((c || root).querySelectorAll(s));

        /* ---------- SERVICE TABS ---------- */
        const tabBtns = $$('#detTabs button');
        const panes = $$('.det-pane');
        const showPane = (key) => {
          tabBtns.forEach(b => b.classList.toggle('on', b.dataset.pane === key));
          panes.forEach(p => p.classList.toggle('on', p.dataset.pane === key));
        };
        tabBtns.forEach(b => b.addEventListener('click', () => showPane(b.dataset.pane)));
        $$('.svc-card').forEach(c => {
          const btn = $('.svc-more', c);
          if (btn) btn.addEventListener('click', () => {
            showPane(c.dataset.tab);
            const det = $('#det'); if (det) det.scrollIntoView({ behavior: 'smooth' });
          });
        });

              /* ---------- COUNTERS ---------- */
        function animateCount(el) {
          const target = +el.dataset.count, suffix = el.dataset.suffix || '';
          let cur = 0; const step = Math.max(1, Math.ceil(target / 60));
          const t = setInterval(() => {
            cur += step; if (cur >= target) { cur = target; clearInterval(t); }
            el.textContent = cur.toLocaleString('en-IN') + suffix;
          }, 24);
        }

              /* ---------- SCROLL REVEAL (fade / zoom / left / right / flip) ---------- */
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const io = new IntersectionObserver((entries) => {
          entries.forEach(e => {
            if (e.isIntersecting) {
              e.target.classList.add('in');
              if (e.target.querySelectorAll) e.target.querySelectorAll('[data-count]').forEach(n => { if (!n.dataset.done) { n.dataset.done = 1; animateCount(n); } });
              if (e.target.matches('[data-count]') && !e.target.dataset.done) { e.target.dataset.done = 1; animateCount(e.target); }
              io.unobserve(e.target);
            }
          });
        }, { threshold: 0.18 });
        $$('.reveal').forEach(el => reduce ? el.classList.add('in') : io.observe(el));
        $$('[data-count]').forEach(el => io.observe(el));


    },
});

export default publicWidget.registry.WatsonSite;
