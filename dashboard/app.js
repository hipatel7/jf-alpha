const buyTable = document.getElementById("buyTable");
const sellTable = document.getElementById("sellTable");
const fullTable = document.getElementById("fullTable");
const asOf = document.getElementById("asOf");
const buyCount = document.getElementById("buyCount");
const sellCount = document.getElementById("sellCount");
const universeSize = document.getElementById("universeSize");
const signalName = document.getElementById("signalName");
const searchInput = document.getElementById("searchInput");
const actionFilter = document.getElementById("actionFilter");

let records = [];

function badge(action) {
  const klass = action.toLowerCase();
  return `<span class="badge ${klass}">${action}</span>`;
}

function renderTable(rows) {
  if (!rows.length) {
    return "<p>No records</p>";
  }

  const body = rows
    .map(
      (row) => `
      <tr>
        <td>${row.ticker}</td>
        <td>${row.rank}</td>
        <td>${row.signal_12_1.toFixed(4)}</td>
        <td>${badge(row.action)}</td>
      </tr>
    `
    )
    .join("");

  return `
    <table class="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Rank</th>
          <th>Signal</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${body}
      </tbody>
    </table>
  `;
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

function applyData(data) {
  records = data.records;

  asOf.textContent = `As of ${data.as_of_date}`;
  signalName.textContent = data.signal;
  buyCount.textContent = data.buy_count;
  sellCount.textContent = data.sell_count;
  universeSize.textContent = data.universe_size;

  const buys = records.filter((row) => row.action === "BUY");
  const sells = records.filter((row) => row.action === "SELL");

  buyTable.innerHTML = renderTable(buys);
  sellTable.innerHTML = renderTable(sells);
  refreshFullTable();
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
