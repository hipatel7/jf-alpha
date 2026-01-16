const buyTable = document.getElementById("buyTable");
const sellTable = document.getElementById("sellTable");
const fullTable = document.getElementById("fullTable");
const asOf = document.getElementById("asOf");
const buyCount = document.getElementById("buyCount");
const sellCount = document.getElementById("sellCount");
const universeSize = document.getElementById("universeSize");
const sepaCount = document.getElementById("sepaCount");
const sepaTable = document.getElementById("sepaTable");
const sepaCharts = document.getElementById("sepaCharts");
const analystTable = document.getElementById("analystTable");
const signalName = document.getElementById("signalName");
const searchInput = document.getElementById("searchInput");
const actionFilter = document.getElementById("actionFilter");
const universeTabs = document.getElementById("universeTabs");
const viewTabs = document.getElementById("viewTabs");
const signalSection = document.getElementById("signalSection");
const fullSection = document.getElementById("fullSection");
const sepaSection = document.getElementById("sepaSection");
const sepaChartsSection = document.getElementById("sepaChartsSection");
const analystSection = document.getElementById("analystSection");

let universes = [];
let records = [];
let chartInstances = [];
let activeView = "signals";

const VIEW_OPTIONS = [
  { id: "signals", label: "Signals" },
  { id: "sepa", label: "SEPA" },
  { id: "charts", label: "Charts" },
];

function badge(action) {
  const klass = action.toLowerCase();
  return `<span class="badge ${klass}">${action}</span>`;
}

function renderTable(rows) {
  if (!rows.length) {
    return "<p>No records</p>";
  }

  const body = rows
    .map((row) => {
      const composite =
        row.composite_score !== undefined ? row.composite_score : row.signal_12_1;
      const momentum =
        row.momentum_12_1 !== undefined ? row.momentum_12_1 : row.signal_12_1;
      return `
      <tr>
        <td>${row.ticker}</td>
        <td>${row.rank}</td>
        <td>${Number(composite).toFixed(4)}</td>
        <td>${Number(momentum).toFixed(4)}</td>
        <td>${badge(row.action)}</td>
      </tr>
    `;
    })
    .join("");

  return `
    <table class="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Rank</th>
          <th>Composite</th>
          <th>Momentum</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${body}
      </tbody>
    </table>
  `;
}

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

function renderAnalystTable(rows) {
  if (!rows.length) {
    return "<p>No analyst data</p>";
  }

  const body = rows
    .map(
      (row) => `
      <tr>
        <td>${row.ticker}</td>
        <td>${row.consensus ?? "-"}</td>
        <td>${row.analyst_count ?? "-"}</td>
        <td>${row.target_consensus === null ? "-" : row.target_consensus.toFixed(2)}</td>
        <td>${row.target_low === null ? "-" : row.target_low.toFixed(2)}</td>
        <td>${row.target_high === null ? "-" : row.target_high.toFixed(2)}</td>
      </tr>
    `
    )
    .join("");

  return `
    <table class="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Consensus</th>
          <th>Analysts</th>
          <th>Target</th>
          <th>Low</th>
          <th>High</th>
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

function refreshFullTable() {
  const query = searchInput.value.trim().toUpperCase();
  const filter = actionFilter.value;

  const filtered = records.filter((row) => {
    const matchesTicker = row.ticker.includes(query);
    const matchesAction = filter === "ALL" || row.action === filter;
    return matchesTicker && matchesAction;
  });

  fullTable.innerHTML = renderTable(filtered);
}

function setActiveUniverse(universe) {
  records = universe.records;

  const fundamentalsDate = universe.fundamentals_as_of
    ? ` | Fundamentals ${universe.fundamentals_as_of}`
    : "";
  asOf.textContent = `As of ${universe.as_of_date} | ${universe.name}${fundamentalsDate}`;

  buyCount.textContent = universe.buy_count;
  sellCount.textContent = universe.sell_count;
  universeSize.textContent = universe.universe_size;
  sepaCount.textContent = universe.sepa_count ?? 0;

  const buys = records.filter((row) => row.action === "BUY");
  const sells = records.filter((row) => row.action === "SELL");

  buyTable.innerHTML = renderTable(buys);
  sellTable.innerHTML = renderTable(sells);
  analystTable.innerHTML = renderAnalystTable(universe.analyst_panel || []);
  sepaTable.innerHTML = renderSepaTable(universe.sepa_candidates || []);
  renderCharts(universe.sepa_charts || []);
  refreshFullTable();

  [...universeTabs.children].forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.id === universe.id);
  });
}

function setActiveView(viewId) {
  activeView = viewId;
  const showSignals = viewId === "signals";
  const showSepa = viewId === "sepa";
  const showCharts = viewId === "charts";

  signalSection.classList.toggle("is-hidden", !showSignals);
  fullSection.classList.toggle("is-hidden", !showSignals);
  analystSection.classList.toggle("is-hidden", !showSignals);
  sepaSection.classList.toggle("is-hidden", !showSepa);
  sepaChartsSection.classList.toggle("is-hidden", !showCharts);

  [...viewTabs.children].forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.id === viewId);
  });
}

function renderTabs() {
  universeTabs.innerHTML = universes
    .map(
      (universe) =>
        `<button class="tab" data-id="${universe.id}">${universe.name}</button>`
    )
    .join("");

  universeTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) {
      return;
    }
    const selected = universes.find((u) => u.id === button.dataset.id);
    if (selected) {
      setActiveUniverse(selected);
    }
  });

  viewTabs.innerHTML = VIEW_OPTIONS.map(
    (view) => `<button class="tab" data-id="${view.id}">${view.label}</button>`
  ).join("");

  viewTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) {
      return;
    }
    setActiveView(button.dataset.id);
  });
}

function applyData(data) {
  universes = data.universes || [];
  signalName.textContent = data.signal;

  if (!universes.length) {
    asOf.textContent = "No universes available.";
    return;
  }

  universes = universes.map((universe) => ({
    ...universe,
    as_of_date: data.as_of_date,
    fundamentals_as_of: data.fundamentals_as_of,
  }));

  renderTabs();
  setActiveUniverse(universes[0]);
  setActiveView(activeView);
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
      asOf.textContent = "Failed to load data.";
      fullTable.innerHTML = `<p>Error: ${error}</p>`;
    });
}

searchInput.addEventListener("input", refreshFullTable);
actionFilter.addEventListener("change", refreshFullTable);
