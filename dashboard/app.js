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
const universeTabs = document.getElementById("universeTabs");

let universes = [];
let activeUniverse = null;
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
  activeUniverse = universe;
  records = universe.records;

  const fundamentalsDate = universe.fundamentals_as_of
    ? ` | Fundamentals ${universe.fundamentals_as_of}`
    : "";
  asOf.textContent = `As of ${universe.as_of_date} | ${universe.name}${fundamentalsDate}`;

  buyCount.textContent = universe.buy_count;
  sellCount.textContent = universe.sell_count;
  universeSize.textContent = universe.universe_size;

  const buys = records.filter((row) => row.action === "BUY");
  const sells = records.filter((row) => row.action === "SELL");

  buyTable.innerHTML = renderTable(buys);
  sellTable.innerHTML = renderTable(sells);
  refreshFullTable();

  [...universeTabs.children].forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.id === universe.id);
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
