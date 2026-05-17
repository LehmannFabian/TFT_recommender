const apiStatus = document.querySelector("#apiStatus");
const askForm = document.querySelector("#askForm");
const questionInput = document.querySelector("#questionInput");
const answerOutput = document.querySelector("#answerOutput");
const askState = document.querySelector("#askState");
const compForm = document.querySelector("#compForm");
const compState = document.querySelector("#compState");
const compsList = document.querySelector("#compsList");
const limitInput = document.querySelector("#limitInput");
const minGamesInput = document.querySelector("#minGamesInput");
const loadState = document.querySelector("#loadState");
const adminActions = document.querySelector("#adminActions");
const matchPlayersInput = document.querySelector("#matchPlayersInput");
const matchesPerPlayerInput = document.querySelector("#matchesPerPlayerInput");
let adminToken = "";

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(formatApiError(data.detail, response.status));
  }

  return data;
}

function formatApiError(detail, status) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const path = Array.isArray(item.loc) ? item.loc.join(".") : "request";
        return `${path}: ${item.msg}`;
      })
      .join("; ");
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }

  return `Request failed: ${status}`;
}

function readBoundedInt(input, defaultValue, minValue, maxValue) {
  const value = Number.parseInt(input.value, 10);

  if (!Number.isFinite(value)) {
    input.value = String(defaultValue);
    return defaultValue;
  }

  const boundedValue = Math.min(Math.max(value, minValue), maxValue);
  input.value = String(boundedValue);

  return boundedValue;
}

function setState(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderComps(items) {
  if (!items.length) {
    compsList.innerHTML = '<div class="empty">No comps found.</div>';
    return;
  }

  compsList.innerHTML = items
    .map((comp) => {
      const units = comp.units
        .map((unit) => {
          const itemsText = unit.items.length ? unit.items.map(escapeHtml).join(", ") : "no items";
          const unitName = escapeHtml(unit.name || "Unknown");
          const starLevel = unit.star_level ? ` ${escapeHtml(unit.star_level)}*` : "";

          return `
            <div class="unit">
              <span class="unit-name">${unitName}${starLevel}</span>
              <span class="unit-items">${itemsText}</span>
            </div>
          `;
        })
        .join("");

      const traits = comp.traits
        .map((trait) => `<span class="trait">${escapeHtml(trait.label)}</span>`)
        .join("");

      return `
        <article class="comp-card">
          <header>
            <div>
              <div class="rank">#${escapeHtml(comp.rank)}</div>
              <div class="metrics">
                <span>Avg ${escapeHtml(comp.avg_placement)}</span>
                <span>Top 4 ${escapeHtml(comp.top4_rate)}%</span>
                <span>${escapeHtml(comp.games)} Games</span>
                <span>${escapeHtml(comp.wins)} Wins</span>
                <span>Level ${escapeHtml(comp.level)}</span>
              </div>
            </div>
            <div class="status-pill">Best ${escapeHtml(comp.best_placement)}</div>
          </header>
          <div class="units">${units}</div>
          <div class="traits">${traits || '<span class="trait">No active traits</span>'}</div>
        </article>
      `;
    })
    .join("");
}

async function loadComps() {
  setState(compState, "Loading");

  try {
    const params = new URLSearchParams({
      limit: limitInput.value,
      min_games: minGamesInput.value,
    });
    const data = await requestJson(`/api/comps?${params.toString()}`);
    renderComps(data.items);
    setState(compState, "Ready");
  } catch (error) {
    compsList.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    setState(compState, "Error", true);
  }
}

async function checkApi() {
  try {
    await requestJson("/api/health");
    const config = await requestJson("/api/config");
    apiStatus.textContent = "API online";
    apiStatus.classList.add("ok");

    if (config.admin_enabled) {
      adminToken = window.localStorage.getItem("tft_admin_token") || "";
      adminActions.hidden = false;
      setState(loadState, adminToken ? "Admin ready" : "Admin token missing");
    } else {
      adminActions.hidden = true;
      setState(loadState, "Demo mode");
    }
  } catch {
    apiStatus.textContent = "API offline";
    apiStatus.classList.add("error");
  }
}

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setState(askState, "Generating");
  answerOutput.textContent = "Loading...";

  try {
    const data = await requestJson("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question: questionInput.value.trim() }),
    });
    answerOutput.textContent = data.answer;
    setState(askState, "Ready");
  } catch (error) {
    answerOutput.textContent = error.message;
    setState(askState, "Error", true);
  }
});

compForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadComps();
});

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    const action = button.dataset.action;
    const originalText = button.textContent;
    adminToken = window.localStorage.getItem("tft_admin_token") || "";
    button.disabled = true;
    setState(loadState, "Loading");

    try {
      const body =
        action === "matches"
          ? JSON.stringify({
              max_players_per_rank: readBoundedInt(matchPlayersInput, 1, 1, 100),
              matches_per_player: readBoundedInt(matchesPerPlayerInput, 1, 1, 50),
            })
          : undefined;

      const data = await requestJson(`/api/load/${action}`, {
        method: "POST",
        headers: adminToken ? { "X-Admin-Token": adminToken } : {},
        body,
      });
      setState(
        loadState,
        action === "matches" && data.players
          ? `Done: ${data.stored_matches}/${data.downloaded_matches} matches, ${data.stored_boards} boards`
          : "Done"
      );
      await loadComps();
    } catch (error) {
      setState(loadState, error.message, true);
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
});

checkApi();
