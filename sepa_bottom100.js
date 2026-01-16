const asOf = document.getElementById("asOf");
const signalName = document.getElementById("signalName");
const universeSize = document.getElementById("universeSize");
const sepaCount = document.getElementById("sepaCount");
const sepaTable = document.getElementById("sepaTable");
const sepaCharts = document.getElementById("sepaCharts");

let chartInstances = [];

function renderSepaTable(rows) {
  if (!rows.length) {
    return "<p>No SEPA candidates</p>";
  }

  const body = rows
    .map(
      (row) => `
      <tr>
        <td>${row.ticker}</td>
        <td>${row.rs_score === null ? "-" : row.rs_score.toFixed(4)}</td>
        <td>${row.ma_50 === null ? "-" : row.ma_50.toFixed(2)}</td>
        <td>${row.ma_150 === null ? "-" : row.ma_150.toFixed(2)}</td>
        <td>${row.ma_200 === null ? "-" : row.ma_200.toFixed(2)}</td>
      </tr>
    `
    )
    .join("");

  return `
    <table class="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>RS Score</th>
          <th>MA 50</th>
          <th>MA 150</th>
          <th>MA 200</th>
        </tr>
      </thead>
      <tbody>
        ${body}
      </tbody>
    </table>
  `;
}

function renderCharts(charts) {
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];

  if (!charts.length) {
    sepaCharts.innerHTML = "<p>No charts available</p>";
    return;
  }

  sepaCharts.innerHTML = charts
    .map(
      (item, index) => `
      <div class="chart-card">
        <h3>${item.ticker}</h3>
        <p class="chart-meta">RS score: ${
          item.rs_score === null ? "-" : item.rs_score.toFixed(4)
        }</p>
        <canvas id="chart-${index}" height="180"></canvas>
      </div>
    `
    )
    .join("");

  charts.forEach((item, index) => {
    const ctx = document.getElementById(`chart-${index}`);
    const data = {
      labels: item.dates,
      datasets: [
        {
          label: "Close",
          data: item.close,
          borderColor: "#1b1a17",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
        },
        {
          label: "MA 50",
          data: item.ma50,
          borderColor: "#0f5132",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
        },
        {
          label: "MA 150",
          data: item.ma150,
          borderColor: "#b4572b",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
        },
        {
          label: "MA 200",
          data: item.ma200,
          borderColor: "#6d6457",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
        },
      ],
    };

    if (item.rs_line && item.rs_line.some((val) => val !== null)) {
      data.datasets.push({
        label: "RS Line",
        data: item.rs_line,
        borderColor: "#2a6f97",
        borderDash: [6, 4],
        borderWidth: 1,
        pointRadius: 0,
        tension: 0.2,
        yAxisID: "y1",
      });
    }

    const chart = new Chart(ctx, {
      type: "line",
      data,
      options: {
        responsive: true,
        scales: {
          x: {
            ticks: {
              maxTicksLimit: 6,
            },
          },
          y: {
            position: "left",
            ticks: {
              maxTicksLimit: 5,
            },
          },
          y1: {
            position: "right",
            grid: {
              drawOnChartArea: false,
            },
            ticks: {
              maxTicksLimit: 5,
            },
          },
        },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
            },
          },
        },
      },
    });

    chartInstances.push(chart);
  });
}

function applyData(data) {
  const universe = (data.universes || []).find(
    (item) => item.id === "sp500_bottom100"
  );

  if (!universe) {
    asOf.textContent = "Bottom 100 universe not found.";
    return;
  }

  const fundamentalsDate = data.fundamentals_as_of
    ? ` | Fundamentals ${data.fundamentals_as_of}`
    : "";
  asOf.textContent = `As of ${data.as_of_date} | ${universe.name}${fundamentalsDate}`;

  signalName.textContent = data.signal;
  universeSize.textContent = universe.universe_size;
  sepaCount.textContent = universe.sepa_count ?? 0;

  sepaTable.innerHTML = renderSepaTable(universe.sepa_candidates || []);
  renderCharts(universe.sepa_charts || []);
}

if (window.TOP50_DATA) {
  applyData(window.TOP50_DATA);
} else {
  fetch("data/top50_signals.json")
    .then((response) => response.json())
    .then((data) => {
      applyData(data);
    })
    .catch((error) => {
      asOf.textContent = `Failed to load data: ${error}`;
    });
}
