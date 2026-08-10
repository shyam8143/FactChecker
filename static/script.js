(() => {
  "use strict";

  const MAX_CHARS = 3000;
  const VERDICT_KEY = {
    TRUE: "true",
    FALSE: "false",
    MISLEADING: "misleading",
    UNVERIFIED: "unverified",
  };

  const $ = (id) => document.getElementById(id);

  const claimInput = $("claimInput");
  const charCount = $("charCount");
  const pasteBtn = $("pasteBtn");
  const checkBtn = $("checkBtn");
  const errorMsg = $("errorMsg");
  const resultWrap = $("resultWrap");
  const resultCard = $("resultCard");
  const verdictBadge = $("verdictBadge");
  const confidenceRing = $("confidenceRing");
  const confidenceText = $("confidenceText");
  const checkedClaim = $("checkedClaim");
  const explanation = $("explanation");
  const sourcesList = $("sources");
  const historyList = $("historyList");
  const clearBtn = $("clearBtn");
  const langBtns = document.querySelectorAll(".lang-btn");

  let currentLang = "en";
  let checking = false;

  const setLangBtns = () =>
    langBtns.forEach((b) => b.classList.toggle("active", b.dataset.lang === currentLang));

  langBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      currentLang = btn.dataset.lang;
      setLangBtns();
    });
  });

  claimInput.addEventListener("input", () => {
    const len = claimInput.value.length;
    charCount.textContent = len > MAX_CHARS ? `${len} / ${MAX_CHARS} (too long)` : `${len} / ${MAX_CHARS}`;
    charCount.style.color = len > MAX_CHARS ? "var(--false)" : "";
  });

  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      claimInput.value = text.slice(0, MAX_CHARS);
      claimInput.dispatchEvent(new Event("input"));
      claimInput.focus();
    } catch {
      errorMsg.textContent = "Clipboard not accessible. Press Ctrl+V to paste.";
      errorMsg.classList.remove("hidden");
    }
  });

  clearBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/clear_history", { method: "POST" });
      const data = await res.json();
      renderHistory(data.history);
    } catch {
      /* ignore */
    }
  });

  checkBtn.addEventListener("click", runCheck);

  claimInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") runCheck();
  });

  async function runCheck() {
    if (checking) return;

    const claim = claimInput.value.trim();
    if (!claim) {
      showError("Please enter a claim to fact-check.");
      return;
    }
    if (claim.length > MAX_CHARS) {
      showError("Claim is too long (max 3000 characters).");
      return;
    }

    hideError();
    checking = true;
    checkBtn.disabled = true;
    checkBtn.querySelector(".btn-label").textContent = "Checking...";
    checkBtn.querySelector(".spinner").classList.remove("hidden");

    resultWrap.classList.add("hidden");
    resultCard.classList.add("hidden");

    try {
      const res = await fetch("/api/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim, lang: currentLang }),
      });

      const data = await res.json();
      if (!res.ok) {
        showError(data.error || "Something went wrong. Try again.");
        return;
      }

      renderResult(data.result);
      renderHistory(data.history);
    } catch {
      showError("Network error. Make sure the Flask server is running.");
    } finally {
      checking = false;
      checkBtn.disabled = false;
      checkBtn.querySelector(".btn-label").textContent = "Check this claim";
      checkBtn.querySelector(".spinner").classList.add("hidden");
    }
  }

  function renderResult(r) {
    const key = VERDICT_KEY[r.verdict] || "unverified";

    verdictBadge.textContent = r.verdict;
    verdictBadge.className = "verdict-badge";
    verdictBadge.classList.add(key);

    confidenceText.textContent = `${r.confidence}%`;
    confidenceRing.style.setProperty("--p", Math.max(0, Math.min(100, r.confidence)));

    checkedClaim.textContent = r.claim;
    explanation.textContent = r.explanation;

    sourcesList.innerHTML = "";
    (r.sources || []).forEach((src) => {
      const li = document.createElement("li");
      li.textContent = src;
      sourcesList.appendChild(li);
    });

    resultCard.classList.remove("hidden");
    resultWrap.classList.remove("hidden");
    resultWrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderHistory(history) {
    if (!history || !history.length) {
      historyList.innerHTML = `<p class="empty-state">No checks yet. Paste a claim above to get started!</p>`;
      return;
    }

    historyList.innerHTML = "";
    history.forEach((h) => {
      const key = VERDICT_KEY[h.verdict] || "unverified";
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <span class="h-dot ${key}"></span>
        <div class="h-body">
          <p class="h-claim" title="${escapeHtml(h.claim)}">${escapeHtml(h.claim)}</p>
          <p class="h-meta">${escapeHtml(h.timestamp || "")} &middot; ${h.confidence}% confident</p>
        </div>
        <span class="h-verdict ${key}">${escapeHtml(h.verdict)}</span>`;
      historyList.appendChild(item);
    });
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove("hidden");
  }

  function hideError() {
    errorMsg.classList.add("hidden");
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function init() {
    try {
      const res = await fetch("/api/history");
      const data = await res.json();
      renderHistory(data.history);
    } catch {
      /* server history unavailable */
    }
  }

  init();
})();