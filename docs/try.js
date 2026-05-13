/**
 * healthOS static "Try it" wizard — no server; prompts are copied client-side.
 * Repo + branch come from <meta name="github-repo"> and <meta name="github-branch"> in index.html.
 */
(function () {
  "use strict";

  var COPY_CSV_MAX = 25000;

  function meta(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el && el.getAttribute("content") ? el.getAttribute("content").trim() : "";
  }

  var REPO = meta("github-repo") || "alexshibu1/healthOS";
  var BRANCH = meta("github-branch") || "main";

  function rawPath(pathInRepo) {
    return (
      "https://raw.githubusercontent.com/" +
      REPO +
      "/" +
      BRANCH +
      "/" +
      pathInRepo.replace(/^\//, "")
    );
  }

  var EXTRACTION_URL = rawPath("web/src/data/extraction_prompt.txt");
  var QUICK_ANALYSIS_URL = rawPath("docs/quick_analysis_prompt.md");
  var GITHUB_FILE_EXTRACTION =
    "https://github.com/" + REPO + "/blob/" + BRANCH + "/web/src/data/extraction_prompt.txt";

  var btnTry = document.getElementById("btn-try");
  var modalRoot = document.getElementById("modal-root");
  var modalBackdrop = document.getElementById("modal-backdrop");
  var modalPanel = document.getElementById("modal-panel");
  var modalBody = document.getElementById("modal-body");
  var modalClose = document.getElementById("modal-close");
  var stepIndicator = document.getElementById("step-indicator");

  var step = 1;
  var extractionText = "";
  var extractionFetchError = null;
  var extractionLoading = false;
  var quickAnalysisText = "";
  var quickFetchError = null;
  var csvText = "";
  var fileLabel = "";
  var errorBanner = null;
  var dragActive = false;

  function setFooterUrl() {
    var u = meta("pages-site-url");
    var el = document.getElementById("footer-pages-url");
    if (el && u) el.textContent = u;
  }

  function updateStepIndicator() {
    if (!stepIndicator) return;
    var spans = stepIndicator.querySelectorAll("[data-step]");
    for (var i = 0; i < spans.length; i++) {
      var s = spans[i];
      var n = parseInt(s.getAttribute("data-step"), 10);
      s.classList.remove("current", "done");
      if (n === step) s.classList.add("current");
      else if (n < step) s.classList.add("done");
    }
  }

  function showError(msg) {
    errorBanner = msg;
    render();
  }

  function clearError() {
    errorBanner = null;
  }

  function fetchText(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.text();
    });
  }

  function loadExtraction() {
    if (extractionText || extractionLoading) return Promise.resolve();
    extractionLoading = true;
    extractionFetchError = null;
    render();
    return fetchText(EXTRACTION_URL)
      .then(function (t) {
        extractionText = t.trim();
        extractionLoading = false;
        extractionFetchError = null;
      })
      .catch(function () {
        extractionLoading = false;
        extractionFetchError =
          "Could not load the extraction prompt from GitHub. Open the file in the repo or check your connection.";
        extractionText = "";
      })
      .then(function () {
        render();
      });
  }

  function loadQuickAnalysis() {
    if (quickAnalysisText) return Promise.resolve(quickAnalysisText);
    return fetchText(QUICK_ANALYSIS_URL)
      .then(function (t) {
        quickAnalysisText = t.trim();
        quickFetchError = null;
        return quickAnalysisText;
      })
      .catch(function () {
        quickFetchError = "Could not load quick-analysis instructions from GitHub.";
        quickAnalysisText = [
          "You are helping interpret a health CSV for healthOS (qualitative only).",
          "You are NOT running the Python scorers.",
          "Summarize coverage, data quality notes, three hypothesis-level next steps.",
          "Closing: for NLR×HRV, SRI, decoupling, composite, bio-age, interventions — clone https://github.com/" +
            REPO +
            " and run `make dev` per the README Quickstart.",
        ].join("\n\n");
        return quickAnalysisText;
      });
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return Promise.reject(new Error("Clipboard API unavailable"));
  }

  function render() {
    updateStepIndicator();
    if (!modalBody) return;

    var h = "";
    if (step === 1) {
      h +=
        "<h2>Gather your data</h2>" +
        "<p class=\"small muted\">Collect everything you have — screenshots from health apps, blood work PDFs, " +
        "fitness app exports, notes. You don't need to organize it.</p>" +
        "<p class=\"small muted\">Works with: Apple Health, Garmin, WHOOP, Oura, Strava, blood panels, anything " +
        "you can screenshot or export.</p>" +
        "<p class=\"small muted\">Sharing with someone who doesn't run the stack? Point them to " +
        "<a href=\"https://github.com/" +
        REPO +
        "\">the GitHub repo</a> or this site's <strong>Try it</strong> walkthrough — no install required for the prompt-only path.</p>" +
        "<button type=\"button\" class=\"btn-inline secondary\" id=\"step1-next\">Got it, next →</button>";
    } else if (step === 2) {
      h += "<h2>Ask an LLM to structure it</h2>";
      h +=
        "<p class=\"small muted\">Open Claude, ChatGPT, or any LLM. Share your health data — paste screenshots, " +
        "text, whatever you have. Then copy the extraction prompt below into that chat.</p>";

      if (extractionLoading) {
        h += "<p class=\"small muted\">Loading prompt from GitHub…</p>";
      } else if (extractionFetchError) {
        h +=
          "<p class=\"err\">" +
          escapeHtml(extractionFetchError) +
          "</p>" +
          "<p class=\"small muted\"><a href=\"" +
          GITHUB_FILE_EXTRACTION +
          "\">Open extraction_prompt.txt on GitHub</a> and copy it manually.</p>";
      } else {
        h +=
          "<div style=\"display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.5rem\">" +
          "<button type=\"button\" class=\"btn-inline\" id=\"copy-extraction\">Copy prompt</button>" +
          "</div>" +
          "<pre class=\"prompt-preview\" id=\"extraction-pre\">" +
          escapeHtml(extractionText) +
          "</pre>" +
          "<p class=\"small muted\">The LLM should return a single CSV file. Save it when you're done.</p>";
      }

      h +=
        "<button type=\"button\" class=\"btn\" id=\"step2-next\" " +
        (extractionLoading ? "disabled" : "") +
        ">I have the CSV →</button>";
    } else if (step === 3) {
      h +=
        "<h2>Prepare a quick analysis prompt</h2>" +
        "<p class=\"small muted\">Choose your <code>universal.csv</code> (or equivalent) below. " +
        "Nothing is uploaded — the file is read in your browser only. Then copy the combined prompt " +
        "and paste it into your LLM.</p>" +
        "<p class=\"small muted\">For <strong>scored</strong> NLR×HRV, SRI, decoupling, composite, bio-age, and ranked interventions, " +
        "run the <a href=\"https://github.com/" +
        REPO +
        "\">local pipeline</a> (<code>make dev</code>).</p>";

      h +=
        "<input type=\"file\" accept=\".csv,text/csv\" class=\"sr-only\" id=\"csv-input\" />" +
        "<button type=\"button\" class=\"dropzone" +
        (dragActive ? " drag" : "") +
        "\" id=\"dropzone\">" +
        "<span>Drag & drop CSV here</span>" +
        "<span class=\"mono\" style=\"opacity:0.75;font-size:0.55rem\">or click to choose</span>" +
        "</button>";

      if (fileLabel) {
        h +=
          "<p class=\"mono small muted\" style=\"margin:0\">" +
          escapeHtml(fileLabel) +
          "</p>";
      }

      if (csvText) {
        var truncated = csvText.length > COPY_CSV_MAX;
        var excerpt = truncated ? csvText.slice(0, COPY_CSV_MAX) : csvText;
        h +=
          "<p class=\"small muted\">Excerpt length: " +
          excerpt.length +
          " characters" +
          (truncated ? " (truncated for clipboard)" : "") +
          ".</p>" +
          "<div style=\"display:flex;flex-wrap:wrap;gap:0.5rem\">" +
          "<button type=\"button\" class=\"btn-inline\" id=\"copy-quick\">Copy quick analysis prompt</button>" +
          "</div>" +
          "<p class=\"small muted\">Opens your LLM in a new tab (empty chat — paste after):</p>" +
          "<div class=\"llm-links\">" +
          "<a href=\"https://chatgpt.com/\" target=\"_blank\" rel=\"noopener noreferrer\">ChatGPT</a>" +
          "<a href=\"https://claude.ai/new\" target=\"_blank\" rel=\"noopener noreferrer\">Claude</a>" +
          "<a href=\"https://gemini.google.com/app\" target=\"_blank\" rel=\"noopener noreferrer\">Gemini</a>" +
          "</div>";
      }

      if (errorBanner) {
        h += "<p class=\"err\">" + escapeHtml(errorBanner) + "</p>";
      }
    }

    modalBody.innerHTML = h;
    wireStepHandlers();
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function wireStepHandlers() {
    var el;

    el = document.getElementById("step1-next");
    if (el) {
      el.addEventListener("click", function () {
        clearError();
        step = 2;
        render();
        void loadExtraction();
      });
    }

    el = document.getElementById("copy-extraction");
    if (el && extractionText) {
      el.addEventListener("click", function () {
        clearError();
        copyToClipboard(extractionText)
          .then(function () {
            el.textContent = "Copied";
            setTimeout(function () {
              el.textContent = "Copy prompt";
            }, 2000);
          })
          .catch(function () {
            showError("Could not copy — select the preview text manually.");
          });
      });
    }

    el = document.getElementById("step2-next");
    if (el && !el.disabled) {
      el.addEventListener("click", function () {
        clearError();
        step = 3;
        render();
      });
    }

    var dz = document.getElementById("dropzone");
    var input = document.getElementById("csv-input");
    if (dz && input) {
      dz.addEventListener("click", function () {
        input.click();
      });
      dz.addEventListener("dragenter", function (e) {
        e.preventDefault();
        dragActive = true;
        render();
      });
      dz.addEventListener("dragover", function (e) {
        e.preventDefault();
        dragActive = true;
      });
      dz.addEventListener("dragleave", function (e) {
        e.preventDefault();
        dragActive = false;
        render();
      });
      dz.addEventListener("drop", function (e) {
        e.preventDefault();
        dragActive = false;
        var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) readFile(f);
      });
      input.addEventListener("change", function (e) {
        var f = e.target.files && e.target.files[0];
        if (f) readFile(f);
        input.value = "";
      });
    }

    el = document.getElementById("copy-quick");
    if (el) {
      el.addEventListener("click", function () {
        clearError();
        void loadQuickAnalysis().then(function (qa) {
          var excerpt = csvText.length > COPY_CSV_MAX ? csvText.slice(0, COPY_CSV_MAX) : csvText;
          var note = csvText.length > COPY_CSV_MAX ? "\n\n[CSV truncated for length in this prompt copy.]\n" : "";
          var full =
            qa +
            "\n\n---\n## User CSV (excerpt)\n\n```csv\n" +
            excerpt +
            "\n```" +
            note;
          return copyToClipboard(full).then(function () {
            el.textContent = "Copied";
            setTimeout(function () {
              el.textContent = "Copy quick analysis prompt";
            }, 2000);
          });
        }).catch(function () {
          showError("Could not copy — try a smaller file or copy manually.");
        });
      });
    }
  }

  function readFile(file) {
    clearError();
    var name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && file.type !== "text/csv" && file.type !== "application/csv") {
      showError("Please choose a .csv file.");
      return;
    }
    fileLabel = file.name;
    var reader = new FileReader();
    reader.onload = function () {
      var text = typeof reader.result === "string" ? reader.result : "";
      csvText = text;
      render();
    };
    reader.onerror = function () {
      showError("Could not read file.");
      render();
    };
    reader.readAsText(file, "UTF-8");
  }

  function openModal() {
    step = 1;
    extractionText = "";
    extractionFetchError = null;
    extractionLoading = false;
    quickAnalysisText = "";
    quickFetchError = null;
    csvText = "";
    fileLabel = "";
    clearError();
    dragActive = false;
    modalRoot.classList.remove("hidden");
    modalRoot.setAttribute("aria-hidden", "false");
    render();
  }

  function closeModal() {
    modalRoot.classList.add("hidden");
    modalRoot.setAttribute("aria-hidden", "true");
  }

  if (btnTry) btnTry.addEventListener("click", openModal);
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modalBackdrop) {
    modalBackdrop.addEventListener("click", closeModal);
  }
  if (modalPanel) {
    modalPanel.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  }

  setFooterUrl();
})();
