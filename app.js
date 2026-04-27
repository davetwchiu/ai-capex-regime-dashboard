document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data/latest.json');
        const data = await response.json();

        // Header & Freshness
        document.getElementById('last-updated').textContent = `Latest market data: ${data.data_health.latest_trading_date}`;
        if (data.data_health.is_stale) {
            document.getElementById('stale-warning').classList.remove('hidden');
        }
        document.getElementById('regime-badge').textContent = `Regime ${data.regime !== 'Mixed / Transition' ? data.regime : 'Mixed'}`;

        // Regime Card Logic
        const isMixed = data.regime === "Mixed / Transition";
        document.getElementById('regime-name').textContent = isMixed ? "Mixed / Transition" : `${data.regime} — ${data.regime_name}`;
        
        let closestText = `Closest Profile: ${data.closest_regime.code} (${data.closest_regime.name}) | Confidence: ${data.confidence}`;
        document.getElementById('closest-regime').textContent = closestText;

        // Divergences
        if (data.divergence_warnings && data.divergence_warnings.length > 0) {
            const divSec = document.getElementById('divergences-section');
            const divList = document.getElementById('divergences-list');
            data.divergence_warnings.forEach(w => {
                const li = document.createElement('li');
                li.textContent = w.message;
                divList.appendChild(li);
            });
            divSec.classList.remove('hidden');
        }

        // Data Health
        const dh = data.data_health;
        const statusBadge = document.getElementById('dh-status');
        statusBadge.textContent = dh.status;
        statusBadge.className = 'badge'; // reset
        if (dh.status === 'OK') statusBadge.classList.add('success');
        else if (dh.status === 'Partial') statusBadge.classList.add('warning');
        else statusBadge.classList.add('danger');

        document.getElementById('dh-message').textContent = dh.message;
        document.getElementById('dh-source').textContent = dh.source;
        document.getElementById('dh-date').textContent = dh.latest_trading_date;
        
        // Format UTC date nicely
        const utcDate = new Date(dh.last_updated_utc);
        document.getElementById('dh-updated').textContent = isNaN(utcDate) ? dh.last_updated_utc : utcDate.toLocaleString();
        
        document.getElementById('dh-retrieval').textContent = `${dh.retrieved_tickers} / ${dh.expected_tickers} (${dh.retrieval_success_pct}%)`;
        
        const coreSpan = document.getElementById('dh-core');
        if (dh.core_tickers_ok) {
            coreSpan.textContent = "OK";
            coreSpan.style.color = "var(--success)";
        } else {
            coreSpan.textContent = `Missing (${dh.core_missing_tickers.join(', ')})`;
            coreSpan.style.color = "var(--danger)";
        }

        if (dh.failed_tickers && dh.failed_tickers.length > 0) {
            document.getElementById('dh-failed-container').classList.remove('hidden');
            document.getElementById('dh-failed').textContent = dh.failed_tickers.join(', ');
        }

        // Scores
        const scores = ['demand', 'bottleneck', 'substitution', 'stress', 'breadth'];
        scores.forEach(s => {
            const el = document.getElementById(`score-${s}`);
            el.textContent = data.scores[s];
            if (data.scores[s] >= 60) el.style.color = s === 'stress' ? 'var(--danger)' : 'var(--success)';
            if (data.scores[s] < 40) el.style.color = s === 'stress' ? 'var(--success)' : 'var(--danger)';
        });

        // Regime Matrix Render
        const ctxMatrix = document.getElementById('regimeMatrixChart').getContext('2d');
        const dScore = data.scores.demand;
        const bScore = data.scores.bottleneck;
        const sScore = data.scores.stress;
        const rScore = data.scores.substitution;

        // Bubble Radius mapping based on Stress (min 5, max 20)
        const radius = (sScore / 100) * 15 + 5; 
        
        // Color Opacity mapping based on Rotation (min 0.2, max 1.0)
        const rotationAlpha = 0.2 + (rScore / 100) * 0.8;

        new Chart(ctxMatrix, {
            type: 'bubble',
            data: {
                datasets: [{
                    label: 'Current Setup',
                    data: [{ x: dScore, y: bScore, r: radius }],
                    backgroundColor: `rgba(37, 99, 235, ${rotationAlpha})`,
                    borderColor: '#1d4ed8',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { min: 0, max: 100, title: { display: true, text: 'Demand Score' } },
                    y: { min: 0, max: 100, title: { display: true, text: 'Bottleneck Score' } }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                return [
                                    `Demand: ${dScore}`,
                                    `Bottleneck: ${bScore}`,
                                    `Stress: ${sScore} (Bubble Size)`,
                                    `Rotation: ${rScore} (Opacity)`,
                                    `Regime: ${data.regime !== 'Mixed / Transition' ? data.regime : 'Mixed'}`,
                                    `Closest Profile: ${data.closest_regime.code}`
                                ];
                            }
                        }
                    }
                }
            }
        });

        // Third Axis Readings Helper
        const getLabel = (val) => val >= 60 ? "High" : (val <= 40 ? "Low" : "Neutral");
        const getRotationLabel = (val) => val >= 85 ? "Extreme" : (val >= 60 ? "High" : (val <= 40 ? "Low" : "Neutral"));
        const getBreadthLabel = (val) => val >= 60 ? "Healthy" : (val <= 40 ? "Weak" : "Neutral");

        document.getElementById('ta-stress').textContent = getLabel(sScore);
        document.getElementById('ta-rotation').textContent = getRotationLabel(rScore);
        document.getElementById('ta-breadth').textContent = getBreadthLabel(data.scores.breadth);
        document.getElementById('ta-closest').textContent = `${data.closest_regime.code} (${data.confidence})`;

        // Ratios Table
        const tbody = document.querySelector('#ratios-table tbody');
        for (const [key, val] of Object.entries(data.key_ratios)) {
            const tr = document.createElement('tr');
            const colorClass = val >= 0 ? 'positive' : 'negative';
            const sign = val >= 0 ? '+' : '';
            tr.innerHTML = `<td>${key.replace(/_/g, ' ')}</td><td class="${colorClass}">${sign}${val}%</td>`;
            tbody.appendChild(tr);
        }

        // Fetch History & Render Chart
        fetch('data/history.json').then(res => res.json()).then(histData => {
            if (!histData || histData.length < 3) {
                document.getElementById('history-warning').classList.remove('hidden');
                return;
            }

            const dates = histData.map(d => d.date);
            const ctxHistory = document.getElementById('historyChart').getContext('2d');
            
            new Chart(ctxHistory, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        { label: 'Demand', data: histData.map(d => d.scores.demand), borderColor: '#2563eb', tension: 0.2 },
                        { label: 'Bottleneck', data: histData.map(d => d.scores.bottleneck), borderColor: '#7c3aed', tension: 0.2 },
                        { label: 'Rotation', data: histData.map(d => d.scores.substitution), borderColor: '#059669', tension: 0.2 },
                        { label: 'Stress', data: histData.map(d => d.scores.stress), borderColor: '#dc2626', tension: 0.2 },
                        { label: 'Breadth', data: histData.map(d => d.scores.breadth), borderColor: '#d97706', tension: 0.2 }
                    ]
                },
                options: {
                    responsive: true,
                    scales: { y: { min: 0, max: 100 } },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }
                }
            });
        }).catch(err => console.log("No history data yet.", err));

    } catch (error) {
        document.getElementById('regime-name').textContent = "Error loading data.";
        console.error("Failed to fetch latest.json", error);
    }
});
