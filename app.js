document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data/latest.json');
        const data = await response.json();

        // Header
        document.getElementById('last-updated').textContent = `Date: ${data.date}`;
        document.getElementById('regime-badge').textContent = `Regime ${data.regime}`;

        // Regime Card
        document.getElementById('regime-name').textContent = data.regime_name;
        document.getElementById('regime-summary').textContent = data.summary;

        // Scores
        const scores = ['demand', 'bottleneck', 'substitution', 'stress', 'breadth'];
        scores.forEach(s => {
            const el = document.getElementById(`score-${s}`);
            el.textContent = data.scores[s];
            if (data.scores[s] >= 60) el.style.color = 'var(--success)';
            if (data.scores[s] < 40) el.style.color = 'var(--danger)';
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

        // 2D Regime Map (Chart.js)
        const ctx = document.getElementById('regimeChart').getContext('2d');
        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Current Market State',
                    data: [{ x: data.scores.demand, y: data.scores.bottleneck }],
                    backgroundColor: '#2563eb',
                    pointRadius: (data.scores.stress / 5) + 5 // Bubble size based on stress
                }]
            },
            options: {
                scales: {
                    x: { title: { display: true, text: 'Demand Score (0-100)' }, min: 0, max: 100 },
                    y: { title: { display: true, text: 'Bottleneck Score (0-100)' }, min: 0, max: 100 }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `Demand: ${ctx.raw.x}, Bottleneck: ${ctx.raw.y} (Size = Stress)`
                        }
                    }
                }
            }
        });

    } catch (error) {
        document.getElementById('regime-name').textContent = "Error loading data.";
        console.error("Failed to fetch latest.json", error);
    }
});
