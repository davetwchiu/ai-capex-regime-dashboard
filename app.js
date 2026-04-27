document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data/latest.json', { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Failed to load latest.json: HTTP ${response.status}`);
        }

        const data = await response.json();

        const safeText = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        };

        const show = (id) => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('hidden');
        };

        const scoreLabel = (val) => {
            if (val >= 60) return "High";
            if (val <= 40) return "Low";
            return "Neutral";
        };

        const rotationLabel = (val) => {
            if (val >= 85) return "Extreme";
            if (val >= 60) return "High";
            if (val <= 40) return "Low";
            return "Neutral";
        };

        const breadthLabel = (val) => {
            if (val >= 60) return "Healthy";
            if (val <= 40) return "Weak";
            return "Neutral";
        };

        const hardRegimeLabel = data.regime !== 'Mixed / Transition'
            ? data.regime
            : 'Mixed';

        const scores = {
            demand: Number(data.scores?.demand ?? 0),
            bottleneck: Number(data.scores?.bottleneck ?? 0),
            rotation: Number(data.scores?.substitution ?? 0),
            stress: Number(data.scores?.stress ?? 0),
            breadth: Number(data.scores?.breadth ?? 0)
        };

        // Header and Data Freshness
        const dh = data.data_health || data.data_freshness || {};
        safeText('last-updated', `Latest market data: ${dh.latest_trading_date || data.date || 'Unknown'}`);

        if (dh.is_stale) {
            show('stale-warning');
        }

        safeText('regime-badge', `Regime ${hardRegimeLabel}`);

        // Regime Card
        const isMixed = data.regime === "Mixed / Transition";
        safeText('regime-name', isMixed ? "Mixed / Transition" : `${data.regime} — ${data.regime_name}`);

        if (data.closest_regime) {
            safeText(
                'closest-regime',
                `Closest Profile: ${data.closest_regime.code} (${data.closest_regime.name}) | Confidence: ${data.confidence}`
            );
        }

        // Market Read Fallback Logic
        const marketReadText = data.market_read || data.summary || "No plain-English market interpretation is available for this run.";
        safeText('market-read', marketReadText);

        // Plain English Interpretation
        if (data.interpretation) {
            safeText('interp-plain', data.interpretation.plain_english);
            
            const whyList = document.getElementById('interp-why');
            if (whyList) {
                whyList.innerHTML = '';
                data.interpretation.why.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    whyList.appendChild(li);
                });
            }

            const watchList = document.getElementById('interp-watch');
            if (watchList) {
                watchList.innerHTML = '';
                data.interpretation.watch_next.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    watchList.appendChild(li);
                });
            }

            safeText('interp-investor', data.interpretation.investor_reading);
        } else {
            const whyList = document.getElementById('interp-why');
            if (whyList) whyList.innerHTML = "<li>Not generated in this run.</li>";
            const watchList = document.getElementById('interp-watch');
            if (watchList) watchList.innerHTML = "<li>Not generated in this run.</li>";
            safeText('interp-investor', "Interpretation not available.");
        }

        // Key Divergences
        if (data.divergence_warnings && data.divergence_warnings.length > 0) {
            const divSec = document.getElementById('divergences-section');
            const divList = document.getElementById('divergences-list');

            if (divSec && divList) {
                divList.innerHTML = '';

                data.divergence_warnings.forEach(w => {
                    const li = document.createElement('li');
                    const severity = w.severity ? `[${w.severity}] ` : '';
                    li.textContent = `${severity}${w.message}`;
                    if (w.severity) li.classList.add(`severity-${w.severity}`);
                    divList.appendChild(li);
                });

                divSec.classList.remove('hidden');
            }
        }

        // Data Health
        if (document.getElementById('dh-status')) {
            const statusBadge = document.getElementById('dh-status');
            statusBadge.textContent = dh.status || 'Unknown';
            statusBadge.className = 'badge';

            if (dh.status === 'OK') statusBadge.classList.add('success');
            else if (dh.status === 'Partial') statusBadge.classList.add('warning');
            else statusBadge.classList.add('danger');

            safeText('dh-message', dh.message || 'No data-health message available.');
            safeText('dh-source', dh.source || 'Unknown');
            safeText('dh-date', dh.latest_trading_date || data.date || 'Unknown');

            const utcDate = new Date(dh.last_updated_utc || data.last_updated_utc);
            safeText(
                'dh-updated',
                isNaN(utcDate)
                    ? (dh.last_updated_utc || data.last_updated_utc || 'Unknown')
                    : utcDate.toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
            );

            if (dh.retrieved_tickers !== undefined && dh.expected_tickers !== undefined) {
                safeText(
                    'dh-retrieval',
                    `${dh.retrieved_tickers} / ${dh.expected_tickers} (${dh.retrieval_success_pct}%)`
                );
            }

            const coreSpan = document.getElementById('dh-core');
            if (coreSpan) {
                if (dh.core_tickers_ok) {
                    coreSpan.textContent = "OK";
                    coreSpan.style.color = "var(--success)";
                } else {
                    const missing = dh.core_missing_tickers || [];
                    coreSpan.textContent = missing.length > 0 ? `Missing (${missing.join(', ')})` : 'Not confirmed';
                    coreSpan.style.color = "var(--danger)";
                }
            }

            if (dh.failed_tickers && dh.failed_tickers.length > 0) {
                show('dh-failed-container');
                safeText('dh-failed', dh.failed_tickers.join(', '));
            }
        }

        // Score Cards
        [
            ['demand', scores.demand],
            ['bottleneck', scores.bottleneck],
            ['substitution', scores.rotation],
            ['stress', scores.stress],
            ['breadth', scores.breadth]
        ].forEach(([key, val]) => {
            const el = document.getElementById(`score-${key}`);
            if (!el) return;

            el.textContent = val;

            if (val >= 60) {
                el.style.color = key === 'stress' ? 'var(--danger)' : 'var(--success)';
            } else if (val < 40) {
                el.style.color = key === 'stress' ? 'var(--success)' : 'var(--danger)';
            } else {
                el.style.color = 'var(--text-main)';
            }
        });

        // 2D Regime Matrix with Threshold Lines
        render2DRegimeMatrix(data, scores);

        // Third-Axis Readings
        safeText('ta-stress', scoreLabel(scores.stress));
        safeText('ta-rotation', rotationLabel(scores.rotation));
        safeText('ta-breadth', breadthLabel(scores.breadth));

        if (data.closest_regime) {
            safeText('ta-closest', `${data.closest_regime.code} (${data.confidence})`);
        }

        // Interactive 3D View
        render3DRegimeView(data, scores);

        // Ratios Table
        const tbody = document.querySelector('#ratios-table tbody');
        if (tbody && data.key_ratios) {
            tbody.innerHTML = '';

            for (const [key, val] of Object.entries(data.key_ratios)) {
                const numericVal = Number(val);
                const tr = document.createElement('tr');
                const colorClass = numericVal >= 0 ? 'positive' : 'negative';
                const sign = numericVal >= 0 ? '+' : '';

                tr.innerHTML = `
                    <td>${key.replace(/_/g, ' ')}</td>
                    <td class="${colorClass}">${sign}${numericVal}%</td>
                `;

                tbody.appendChild(tr);
            }
        }

        // History Chart
        renderHistoryChart();

    } catch (error) {
        const regimeName = document.getElementById('regime-name');
        if (regimeName) regimeName.textContent = "Error loading data.";

        console.error("Dashboard failed to load:", error);

        const warning = document.getElementById('warnings-section');
        const warningList = document.getElementById('warnings-list');

        if (warning && warningList) {
            const li = document.createElement('li');
            li.textContent = error.message;
            warningList.appendChild(li);
            warning.classList.remove('hidden');
        }
    }
});


function render2DRegimeMatrix(data, scores) {
    const canvas = document.getElementById('regimeMatrixChart');
    if (!canvas || typeof Chart === 'undefined') return;

    const ctx = canvas.getContext('2d');

    const radius = (scores.stress / 100) * 15 + 6;
    const rotationAlpha = 0.25 + (scores.rotation / 100) * 0.75;

    const thresholdPlugin = {
        id: 'thresholdLines',
        afterDraw(chart) {
            const { ctx, chartArea, scales } = chart;
            if (!chartArea) return;

            const x60 = scales.x.getPixelForValue(60);
            const y60 = scales.y.getPixelForValue(60);

            ctx.save();
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = 'rgba(17, 24, 39, 0.35)';
            ctx.lineWidth = 1;

            ctx.beginPath();
            ctx.moveTo(x60, chartArea.top);
            ctx.lineTo(x60, chartArea.bottom);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(chartArea.left, y60);
            ctx.lineTo(chartArea.right, y60);
            ctx.stroke();

            ctx.setLineDash([]);
            ctx.fillStyle = 'rgba(17, 24, 39, 0.55)';
            ctx.font = '11px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

            ctx.fillText('60 Demand threshold', x60 + 6, chartArea.bottom - 8);
            ctx.fillText('60 Bottleneck threshold', chartArea.left + 8, y60 - 8);

            ctx.restore();
        }
    };

    new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Current Setup',
                data: [{
                    x: scores.demand,
                    y: scores.bottleneck,
                    r: radius
                }],
                backgroundColor: `rgba(37, 99, 235, ${rotationAlpha})`,
                borderColor: '#1d4ed8',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Demand Score' },
                    grid: { color: 'rgba(17, 24, 39, 0.08)' }
                },
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Bottleneck Score' },
                    grid: { color: 'rgba(17, 24, 39, 0.08)' }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: () => [
                            `Demand: ${scores.demand}`,
                            `Bottleneck: ${scores.bottleneck}`,
                            `Stress: ${scores.stress} (bubble size)`,
                            `ASIC / Networking Rotation: ${scores.rotation} (opacity)`,
                            `Breadth: ${scores.breadth}`,
                            `Regime: ${data.regime !== 'Mixed / Transition' ? data.regime : 'Mixed'}`,
                            `Closest Profile: ${data.closest_regime?.code || 'N/A'}`,
                            `Confidence: ${data.confidence || 'N/A'}`
                        ]
                    }
                },
                legend: {
                    display: true
                }
            }
        },
        plugins: [thresholdPlugin]
    });
}


function render3DRegimeView(data, scores) {
    const el = document.getElementById('regime3DChart');
    if (!el) return;

    if (typeof Plotly === 'undefined') {
        el.innerHTML = '<p class="section-note">Interactive 3D view is unavailable because Plotly failed to load.</p>';
        return;
    }

    const currentName = data.regime === 'Mixed / Transition'
        ? `Current: Mixed → closest ${data.closest_regime?.code || 'N/A'}`
        : `Current: ${data.regime}`;

    const currentTrace = {
        type: 'scatter3d',
        mode: 'markers+text',
        name: currentName,
        x: [scores.demand],
        y: [scores.bottleneck],
        z: [scores.stress],
        text: ['Current'],
        textposition: 'top center',
        marker: {
            size: Math.max(8, Math.min(24, 8 + scores.breadth / 5)),
            color: [scores.rotation],
            colorscale: [
                [0, '#94a3b8'],
                [0.5, '#2563eb'],
                [1, '#dc2626']
            ],
            cmin: 0,
            cmax: 100,
            colorbar: {
                title: {
                    text: 'ASIC / Networking<br>Rotation'
                }
            },
            opacity: 0.92,
            line: {
                color: '#111827',
                width: 2
            }
        },
        hovertemplate:
            '<b>Current Market Setup</b><br>' +
            'Demand: %{x}<br>' +
            'Bottleneck: %{y}<br>' +
            'Stress: %{z}<br>' +
            `Rotation: ${scores.rotation}<br>` +
            `Breadth: ${scores.breadth}<br>` +
            `Hard Regime: ${data.regime}<br>` +
            `Closest Profile: ${data.closest_regime?.code || 'N/A'} — ${data.closest_regime?.name || 'N/A'}<br>` +
            `Confidence: ${data.confidence || 'N/A'}<extra></extra>`
    };

    const profileTargets = [
        {
            code: 'A',
            name: 'True Bottleneck Still Tight',
            demand: 75,
            bottleneck: 75,
            stress: 25,
            rotation: 50,
            breadth: 75
        },
        {
            code: 'B',
            name: 'Bottleneck Easing, ROI Holding',
            demand: 60,
            bottleneck: 45,
            stress: 35,
            rotation: 75,
            breadth: 65
        },
        {
            code: 'C',
            name: 'Hardware Late-Cycle Squeeze',
            demand: 40,
            bottleneck: 75,
            stress: 75,
            rotation: 50,
            breadth: 40
        },
        {
            code: 'D',
            name: 'CAPEX Bubble Fear',
            demand: 30,
            bottleneck: 30,
            stress: 80,
            rotation: 60,
            breadth: 30
        }
    ];

    const targetTrace = {
        type: 'scatter3d',
        mode: 'markers+text',
        name: 'Regime Reference Profiles',
        x: profileTargets.map(p => p.demand),
        y: profileTargets.map(p => p.bottleneck),
        z: profileTargets.map(p => p.stress),
        text: profileTargets.map(p => p.code),
        textposition: 'top center',
        marker: {
            size: 7,
            color: '#64748b',
            opacity: 0.45,
            symbol: 'diamond'
        },
        customdata: profileTargets.map(p => [p.name, p.rotation, p.breadth]),
        hovertemplate:
            '<b>Regime %{text}</b><br>' +
            '%{customdata[0]}<br>' +
            'Demand target: %{x}<br>' +
            'Bottleneck target: %{y}<br>' +
            'Stress target: %{z}<br>' +
            'Rotation target: %{customdata[1]}<br>' +
            'Breadth target: %{customdata[2]}<extra></extra>'
    };

    const guideLines = make3DGuideLines();

    const layout = {
        margin: { l: 0, r: 0, t: 20, b: 0 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: true,
        legend: {
            orientation: 'h',
            x: 0,
            y: -0.08
        },
        scene: {
            xaxis: {
                title: 'Demand Score',
                range: [0, 100],
                gridcolor: 'rgba(17, 24, 39, 0.10)',
                zerolinecolor: 'rgba(17, 24, 39, 0.20)'
            },
            yaxis: {
                title: 'Bottleneck Score',
                range: [0, 100],
                gridcolor: 'rgba(17, 24, 39, 0.10)',
                zerolinecolor: 'rgba(17, 24, 39, 0.20)'
            },
            zaxis: {
                title: 'Stress Score',
                range: [0, 100],
                gridcolor: 'rgba(17, 24, 39, 0.10)',
                zerolinecolor: 'rgba(17, 24, 39, 0.20)'
            },
            camera: {
                eye: { x: 1.55, y: 1.65, z: 1.15 }
            },
            aspectmode: 'cube'
        }
    };

    const config = {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d']
    };

    Plotly.newPlot(
        el,
        [currentTrace, targetTrace, ...guideLines],
        layout,
        config
    );
}


function make3DGuideLines() {
    const lineStyle = {
        color: 'rgba(17, 24, 39, 0.30)',
        width: 3,
        dash: 'dash'
    };

    return [
        {
            type: 'scatter3d',
            mode: 'lines',
            name: 'Demand 60 Threshold',
            x: [60, 60],
            y: [0, 100],
            z: [0, 0],
            line: lineStyle,
            hoverinfo: 'skip',
            showlegend: false
        },
        {
            type: 'scatter3d',
            mode: 'lines',
            name: 'Bottleneck 60 Threshold',
            x: [0, 100],
            y: [60, 60],
            z: [0, 0],
            line: lineStyle,
            hoverinfo: 'skip',
            showlegend: false
        },
        {
            type: 'scatter3d',
            mode: 'lines',
            name: 'Stress 60 Threshold',
            x: [0, 0],
            y: [0, 100],
            z: [60, 60],
            line: {
                color: 'rgba(220, 38, 38, 0.30)',
                width: 3,
                dash: 'dash'
            },
            hoverinfo: 'skip',
            showlegend: false
        }
    ];
}


async function renderHistoryChart() {
    try {
        const res = await fetch('data/history.json', { cache: 'no-store' });
        if (!res.ok) throw new Error(`history.json HTTP ${res.status}`);

        const histData = await res.json();

        if (!histData || histData.length < 3) {
            const warning = document.getElementById('history-warning');
            if (warning) warning.classList.remove('hidden');
            return;
        }

        const canvas = document.getElementById('historyChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const dates = histData.map(d => d.date);
        const ctxHistory = canvas.getContext('2d');

        new Chart(ctxHistory, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Demand',
                        data: histData.map(d => d.scores.demand),
                        borderColor: '#2563eb',
                        tension: 0.2
                    },
                    {
                        label: 'Bottleneck',
                        data: histData.map(d => d.scores.bottleneck),
                        borderColor: '#7c3aed',
                        tension: 0.2
                    },
                    {
                        label: 'Rotation',
                        data: histData.map(d => d.scores.substitution),
                        borderColor: '#059669',
                        tension: 0.2
                    },
                    {
                        label: 'Stress',
                        data: histData.map(d => d.scores.stress),
                        borderColor: '#dc2626',
                        tension: 0.2
                    },
                    {
                        label: 'Breadth',
                        data: histData.map(d => d.scores.breadth),
                        borderColor: '#d97706',
                        tension: 0.2
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        min: 0,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.log("No history data yet.", err);
        const warning = document.getElementById('history-warning');
        if (warning) warning.classList.remove('hidden');
    }
}
