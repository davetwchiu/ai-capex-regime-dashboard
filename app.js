document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data/latest.json');
        const data = await response.json();

        // Header & Freshness
        document.getElementById('last-updated').textContent = `Latest market data: ${data.data_freshness.latest_trading_date}`;
        if (data.data_freshness.is_stale) {
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

        // Scores
        const scores = ['demand', 'bottleneck', 'substitution', 'stress', 'breadth'];
        scores.forEach(s => {
            const el = document.getElementById(`score-${s}`);
            el.textContent = data.scores[s];
            if (data.scores[s] >= 60) el.style.color = s === 'stress' ? 'var(--danger)' : 'var(--success)';
            if (data.scores[s] < 40) el.style.color = s === 'stress' ? 'var(--success)' : 'var(--danger)';
        });

        // Ratios Table
        const tbody = document.querySelector('#ratios-table tbody');
        for (const [key, val] of Object.entries(data.key_ratios)) {
            const tr = document.createElement('tr');
            const colorClass = val >= 0 ? 'positive' : 'negative';
            const sign = val >= 0 ? '+' : '';
            tr.innerHTML = `<td>${key.replace(/_/g, ' ')}</td><td class="${colorClass}">${sign}${val}%</td>`;
            tbody.appendChild(tr);
        }

        // Warnings
        if (data.warnings && data.warnings.length > 0) {
            const wSec = document.getElementById('warnings-section');
            const wList = document.getElementById('warnings-list');
            data.warnings.forEach(w => {
                const li = document.createElement('li');
                li.textContent = `${w.ticker}: ${w.issue}`;
                wList.appendChild(li);
            });
            wSec.classList.remove('hidden');
        }

        // Fetch History & Render Chart
        fetch('data/history.json').then(res => res.json()).then(histData => {
            if (!histData || histData.length < 3) {
                document.getElementById('history-warning').classList.remove('hidden');
                return;
            }

            const dates = histData.map(d => d.date);
            const ctx = document.getElementById('historyChart').getContext('2d');
            
            new Chart(ctx, {
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
