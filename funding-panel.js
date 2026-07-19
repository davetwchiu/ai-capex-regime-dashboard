(() => {
    "use strict";

    const escapeHtml = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    const fmt = (value, digits = 0) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "--";
    const pct = (value) => Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(0)}%` : "--";
    const statusClass = (status = "") => String(status).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    function injectStyles() {
        const style = document.createElement("style");
        style.textContent = `
            .funding-confirmation-card h3 { margin-top: 0; }
            .funding-head { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
            .funding-head p { margin:4px 0 0; color:var(--text-muted); font-size:14px; }
            .funding-status { text-align:right; min-width:150px; }
            .funding-status strong { display:block; font-size:26px; color:var(--primary); }
            .funding-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; }
            .funding-signal { border:1px solid var(--border); border-radius:8px; padding:12px; background:#f9fafb; }
            .funding-signal span, .funding-signal small { display:block; color:var(--text-muted); font-size:12px; }
            .funding-signal strong { display:block; margin:4px 0; font-size:24px; }
            .funding-note { margin:14px 0 0; padding:10px 12px; background:#f3f4f6; border-left:4px solid var(--primary); font-size:13px; }
            .funding-meta { margin-top:10px; color:var(--text-muted); font-size:12px; }
            .funding-pill { display:inline-block; padding:3px 8px; border-radius:12px; color:#fff; background:var(--primary); font-size:11px; font-weight:600; }
            .funding-pill.confirmed, .funding-pill.supportive, .funding-pill.normal { background:var(--success); }
            .funding-pill.partial, .funding-pill.watch { background:var(--warning); }
            .funding-pill.contradicted, .funding-pill.stress, .funding-pill.credit-stress-confirmed { background:var(--danger); }
            .funding-pill.unmonitored, .funding-pill.not-confirmed { background:#6b7280; }
            @media (max-width:768px) {
                .funding-head { flex-direction:column; }
                .funding-status { text-align:left; }
                .funding-grid { grid-template-columns:1fr; }
            }
        `;
        document.head.appendChild(style);
    }

    function signalCard(title, score, status, detail) {
        return `<div class="funding-signal">
            <span>${escapeHtml(title)}</span>
            <strong>${fmt(score)}</strong>
            <span class="funding-pill ${statusClass(status)}">${escapeHtml(status || "UNMONITORED")}</span>
            <small>${escapeHtml(detail || "")}</small>
        </div>`;
    }

    async function render() {
        injectStyles();
        let latest;
        try {
            const response = await fetch("data/latest.json", { cache: "no-store" });
            latest = await response.json();
        } catch (error) {
            console.error("Unable to load funding confirmation", error);
            return;
        }
        const funding = latest.funding_confirmation;
        if (!funding) return;

        const signals = funding.signals || {};
        const panel = document.createElement("section");
        panel.className = "card funding-confirmation-card";
        panel.id = "funding-confirmation";
        panel.innerHTML = `<div class="funding-head">
            <div>
                <h3>Funding & Credit Confirmation</h3>
                <p>External confirmation layer from the AI Infrastructure Stress Cockpit. It does not alter the five market-derived scores or hard regime classification.</p>
            </div>
            <div class="funding-status">
                <strong>${escapeHtml(funding.status || "UNMONITORED")}</strong>
                <span class="funding-pill ${statusClass(funding.status)}">Confidence ${escapeHtml(funding.confidence_action || "unchanged")}</span>
            </div>
        </div>
        <div class="funding-grid">
            ${signalCard("Hyperscaler funding", signals.hyperscaler_funding_score, signals.hyperscaler_status, `Coverage ${pct(signals.hyperscaler_coverage_ratio)}`)}
            ${signalCard("Neocloud financing", signals.neocloud_financing_score, signals.neocloud_status, "Borrower-side financing and balance-sheet pressure")}
            ${signalCard("Market plumbing", signals.market_plumbing_score, signals.market_plumbing_status, "Price-based liquidation and positioning confirmation")}
        </div>
        <p class="funding-note">${escapeHtml(funding.summary || "Funding confirmation unavailable.")}</p>
        <p class="funding-meta">Core confidence: ${escapeHtml(funding.core_confidence || "--")} · Adjusted confidence: ${escapeHtml(funding.adjusted_confidence || "--")} · Source as of: ${escapeHtml(funding.source_as_of || "--")} · Sync: ${escapeHtml(funding.sync_status || "unknown")}</p>`;

        const anchor = document.getElementById("interpretation-section");
        anchor?.insertAdjacentElement("afterend", panel);
    }

    document.addEventListener("DOMContentLoaded", render);
})();
