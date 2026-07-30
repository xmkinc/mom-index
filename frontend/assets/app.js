/* 宝妈指数 dashboard app — schema v2 renderer
 * Handles: loading, error, empty/insufficient-history, degraded/stale,
 * chart-failure fallback, client-side staleness, honest source labels.
 */
(function () {
  "use strict";

  var SECTOR_NAMES = {
    nasdaq: "纳斯达克",
    gold: "黄金",
    cpo: "CPO通信",
    semiconductor: "半导体",
  };
  var SECTOR_COLORS = {
    nasdaq: "#06b6d4",
    gold: "#fbbf24",
    cpo: "#a78bfa",
    semiconductor: "#34d399",
  };
  var SECTOR_EMOJI = {
    nasdaq: "📈",
    gold: "🥇",
    cpo: "🔌",
    semiconductor: "💾",
  };

  var DATA_PATH = "data/dashboard_data.json";
  var chartInstances = {};

  function $(id) { return document.getElementById(id); }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /* Convert a UTC ISO timestamp to Asia/Shanghai display string. */
  function formatShanghaiTime(isoStr) {
    if (!isoStr) return "—";
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return "—";
      // Asia/Shanghai = UTC+8, no DST.
      var ms = d.getTime() + 8 * 3600 * 1000;
      var sd = new Date(ms);
      var yyyy = sd.getUTCFullYear();
      var mm = String(sd.getUTCMonth() + 1).padStart(2, "0");
      var dd = String(sd.getUTCDate()).padStart(2, "0");
      var hh = String(sd.getUTCHours()).padStart(2, "0");
      var mi = String(sd.getUTCMinutes()).padStart(2, "0");
      return yyyy + "-" + mm + "-" + dd + " " + hh + ":" + mi + " (北京时间)";
    } catch (e) {
      return "—";
    }
  }

  /* Recompute staleness in the browser from generated_at + stale_after_hours. */
  function computeClientStale(payload) {
    try {
      var gen = payload && payload.generated_at;
      var hours = (payload && payload.freshness && payload.freshness.stale_after_hours) || 12;
      if (!gen) return { stale: true, reason: "no-generated-at" };
      var genDate = new Date(gen);
      if (isNaN(genDate.getTime())) return { stale: true, reason: "bad-generated-at" };
      var ageMs = Date.now() - genDate.getTime();
      var ageHours = ageMs / 3600000;
      return { stale: ageHours > hours, reason: ageHours > hours ? "age>" + hours + "h" : "fresh", ageHours: ageHours };
    } catch (e) {
      return { stale: true, reason: "compute-error" };
    }
  }

  function signalClass(idx) {
    if (idx == null || isNaN(idx)) return "gray";
    if (idx >= 75) return "red";
    if (idx >= 60) return "orange";
    if (idx >= 40) return "yellow";
    if (idx >= 20) return "green";
    return "blue";
  }

  function modeBadge(src) {
    var mode = src.mode || "unavailable";
    var label = src.label || src.id || "";
    var modeText = { live: "实时", simulated: "模拟", unavailable: "不可用" }[mode] || mode;
    return '<span class="badge ' + mode + '" title="' + escapeHtml(label) + " · " + modeText +
      '"><span class="dot"></span>' + escapeHtml(label) + " · " + modeText + "</span>";
  }

  function renderStatus(payload, clientStale) {
    var bar = $("status-bar");
    var parts = [];

    var isStale = (payload.freshness && payload.freshness.is_stale) || clientStale.stale;
    var lastSuccess = payload.freshness && payload.freshness.last_success_at;

    if (payload.sources && payload.sources.length) {
      parts.push('<div class="badges">' + payload.sources.map(modeBadge).join("") + "</div>");
    }

    if (isStale) {
      parts.push('<div class="banner stale">⚠️ 数据处于过期/降级状态。' +
        (lastSuccess ? "上次成功采集：" + escapeHtml(formatShanghaiTime(lastSuccess)) : "尚无成功的实时采集记录。") +
        "</div>");
    }
    if (payload.warnings && payload.warnings.length) {
      parts.push('<div class="banner warn"><ul class="warnings">' +
        payload.warnings.map(function (w) { return "<li>" + escapeHtml(w) + "</li>"; }).join("") +
        "</ul></div>");
    }

    bar.innerHTML = parts.join("");
  }

  function renderUpdateTime(payload) {
    $("update-time").textContent =
      "数据生成于 " + formatShanghaiTime(payload.generated_at) +
      (payload.freshness && payload.freshness.last_success_at
        ? " · 上次成功 " + formatShanghaiTime(payload.freshness.last_success_at)
        : "");
  }

  function buySellRatioText(d) {
    // Per design: null when sell_count=0, UI renders ∞.
    if (d.buy_sell_ratio == null) return "∞";
    return String(Number(d.buy_sell_ratio).toFixed(2));
  }

  function renderCards(payload) {
    var container = $("cards");
    var latest = payload.latest;
    if (!latest || !latest.sectors) {
      container.setAttribute("aria-busy", "false");
      container.innerHTML = '<div class="state"><span class="icon">📭</span>暂无可用指数数据。<br>历史数据不足或数据源当前不可用，将在下次成功采集后更新。</div>';
      return;
    }

    container.setAttribute("aria-busy", "false");
    container.innerHTML = Object.keys(latest.sectors).map(function (key) {
      var sector = latest.sectors[key];
      var d = sector.details || {};
      var buyCount = d.buy_count || 0;
      var sellCount = d.sell_count || 0;
      var total = Math.max(buyCount, sellCount, 1);
      var buyPct = (buyCount / total) * 100;
      var ratio = buySellRatioText(d);
      var ratioDesc = d.buy_sell_ratio == null ? "🩸卖方缺失" : (d.buy_sell_ratio > 1.5 ? "🔥追涨" : (d.buy_sell_ratio > 0.8 ? "⚖️平衡" : "🩸恐慌"));
      return "" +
        '<div class="card ' + key + '">' +
          '<div class="sector-name">' + (SECTOR_EMOJI[key] || "") + " " + escapeHtml(SECTOR_NAMES[key] || key) + "</div>" +
          '<div class="index-value">' + (sector.index != null ? Number(sector.index).toFixed(0) : "—") + "</div>" +
          '<div class="index-label">宝妈指数</div>' +
          '<div class="signal ' + signalClass(sector.index) + '">' + escapeHtml(sector.interpretation || "") + "</div>" +
          '<div class="sub-index">' +
            '<div class="buy"><div class="num">' + (d.mom_buy_index != null ? Number(d.mom_buy_index).toFixed(0) : "0") + '</div><div class="lbl">🟢 宝妈买入</div></div>' +
            '<div class="sell"><div class="num">' + (d.mom_sell_index != null ? Number(d.mom_sell_index).toFixed(0) : "0") + '</div><div class="lbl">🔴 宝妈卖出</div></div>' +
          "</div>" +
          '<div class="ratio-row">' +
            "<span>卖 " + sellCount + '</span><div class="bar"><div style="width:' + buyPct + '%"></div></div><span>买 ' + buyCount + "</span>" +
          "</div>" +
          '<div class="detail-row"><span>买卖比</span><span>' + escapeHtml(ratio) + " " + ratioDesc + "</span></div>" +
          '<div class="detail-row"><span>小白帖</span><span>' + (d.newbie_posts || 0) + "/" + (d.valid_posts || d.total_posts || 0) + " (" + (d.newbie_ratio != null ? Number(d.newbie_ratio).toFixed(0) : 0) + "%)</span></div>" +
          '<div class="detail-row"><span>平均情绪</span><span>' + (d.avg_sentiment != null ? Number(d.avg_sentiment).toFixed(0) : "—") + "</span></div>" +
        "</div>";
    }).join("");
  }

  function chartFallback(sector, records) {
    // Rendered when Chart.js is unavailable or fails. Honest, no invented curves.
    if (!records || !records.length) {
      return '<div class="chart-fallback"><p>暂无历史数据。</p></div>';
    }
    var rows = records.slice().reverse().map(function (r) {
      return "<tr><td>" + escapeHtml(r.date) + "</td><td class=\"num\">" + Number(r.index).toFixed(0) +
        '</td><td><span class="badge ' + (r.source_mode === "live" ? "live" : "simulated") + '" style="font-size:10px">' +
        (r.source_mode === "live" ? "实时" : "模拟") + "</span></td></tr>";
    }).join("");
    return '<div class="chart-fallback"><p>图表组件不可用，显示历史数值表：</p><table><thead><tr><th>日期</th><th>指数</th><th>来源</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
  }

  function renderCharts(payload) {
    var container = $("charts");
    var history = payload.sector_history || {};
    var chartAvailable = typeof window.Chart === "function";

    container.innerHTML = Object.keys(SECTOR_NAMES).map(function (key) {
      var records = history[key] || [];
      var emoji = SECTOR_EMOJI[key] || "";
      var name = SECTOR_NAMES[key];
      return '<div class="chart-box" id="chart-box-' + key + '"><h3>' + emoji + " " + escapeHtml(name) + " — 宝妈指数走势</h3>" +
        '<div id="chart-slot-' + key + '">' + (chartAvailable ? "" : chartFallback(key, records)) + "</div></div>";
    }).join("");

    if (!chartAvailable) return;

    Object.keys(SECTOR_NAMES).forEach(function (key) {
      var records = (history[key] || []);
      var slot = $("chart-slot-" + key);
      if (!slot) return;
      if (!records.length) {
        slot.innerHTML = '<div class="chart-fallback"><p>暂无历史数据，将在采集到足够数据后显示趋势。</p></div>';
        return;
      }
      try {
        var canvas = document.createElement("canvas");
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", SECTOR_NAMES[key] + " 宝妈指数历史走势");
        canvas.id = "chart-canvas-" + key;
        slot.innerHTML = "";
        slot.appendChild(canvas);
        var color = SECTOR_COLORS[key] || "#94a3b8";
        chartInstances[key] = new window.Chart(canvas.getContext("2d"), {
          type: "line",
          data: {
            labels: records.map(function (r) { return r.date.slice(5); }),
            datasets: [{
              label: SECTOR_NAMES[key],
              data: records.map(function (r) { return r.index; }),
              borderColor: color,
              backgroundColor: color + "20",
              borderWidth: 2,
              fill: true,
              tension: 0.3,
              pointRadius: 2,
              pointHoverRadius: 5,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: "#1e293b",
                titleColor: "#e2e8f0",
                bodyColor: "#cbd5e1",
                borderColor: "#334155",
                borderWidth: 1,
                callbacks: { label: function (ctx) { return "宝妈指数: " + ctx.parsed.y; } },
              },
            },
            scales: {
              y: { min: 0, max: 100, grid: { color: "#33415533" }, ticks: { color: "#64748b" } },
              x: { grid: { color: "#33415533" }, ticks: { color: "#64748b", maxTicksLimit: 8 } },
            },
          },
        });
      } catch (e) {
        slot.innerHTML = chartFallback(key, records);
      }
    });
  }

  function renderTopPosts(payload) {
    var container = $("top-posts");
    var state = $("top-posts-state");
    var latest = payload.latest;

    if (!latest || !latest.sectors) {
      if (state) state.textContent = "暂无数据。";
      return;
    }

    var allTop = [];
    Object.keys(latest.sectors).forEach(function (key) {
      var posts = (latest.sectors[key].top_newbie_posts) || [];
      posts.forEach(function (p) {
        allTop.push({
          title: p.title || "",
          score: p.score != null ? p.score : 0,
          level: p.level || "",
          reasoning: p.reasoning || "",
          intent: p.intent || "neutral",
          key_signals: p.key_signals || [],
          source_url: p.source_url || "",
          sector: SECTOR_NAMES[key],
        });
      });
    });
    allTop.sort(function (a, b) { return b.score - a.score; });
    allTop = allTop.slice(0, 8);

    // Replace innerHTML entirely (fixes the old spinner-forever bug).
    var body = "";
    if (!allTop.length) {
      body = '<div class="state" id="top-posts-state">今日暂无典型小白帖，或数据源处于不可用状态。</div>';
    } else {
      body = allTop.map(function (p) {
        // The classifier is the source of truth for the human-readable level.
        // Re-deriving it from the numeric score here can drift when backend
        // thresholds change and would make the badge contradict the reasoning.
        var badgeTxt = p.level || (p.score >= 50 ? "纯小白" : "偏小白");
        var badgeCls = badgeTxt === "纯小白" ? "pure" : "semi";
        var intentMap = { buy: "看涨", sell: "看跌", neutral: "中性" };
        var intentTxt = intentMap[p.intent] || "中性";
        var titleHtml;
        if (p.source_url) {
          titleHtml = '<a href="' + escapeHtml(p.source_url) + '" target="_blank" rel="noopener noreferrer nofollow">' + escapeHtml(p.title) + "</a>";
        } else {
          titleHtml = escapeHtml(p.title);
        }
        var signals = (p.key_signals || []).map(function (s) {
          return "<span>▸ " + escapeHtml(s) + "</span>";
        }).join("");
        return "" +
          '<div class="post-item">' +
            '<div class="post-title-line">' +
              '<span class="post-badge ' + badgeCls + '">' + escapeHtml(badgeTxt) + " " + Number(p.score).toFixed(0) + "分</span>" +
              '<span class="intent-tag ' + p.intent + '">' + intentTxt + "</span>" +
              '<span class="post-meta">[' + escapeHtml(p.sector) + "]</span> " +
              titleHtml +
            "</div>" +
            (p.reasoning ? '<div class="post-reason">📝 ' + escapeHtml(p.reasoning) + "</div>" : "") +
            (signals ? '<div class="post-signals">' + signals + "</div>" : "") +
          "</div>";
      }).join("");
    }
    // Keep the heading, replace the state + items.
    var heading = "<h3>🔥 今日最\"小白\"的帖子</h3>";
    container.innerHTML = heading + body;
  }

  function renderMethodology(payload) {
    var m = payload.methodology;
    var box = $("methodology");
    var body = $("methodology-body");
    if (!m) { box.hidden = true; return; }
    var w = m.weights || {};
    var wLines = Object.keys(w).map(function (k) {
      var label = {
        newbie_ratio: "小白占比",
        newbie_intensity: "小白强度",
        sentiment_extremity: "情绪极端度",
        purity: "纯度信号",
        activity: "活跃度",
      }[k] || k;
      return "<li>" + escapeHtml(label) + " — 权重 " + Number(w[k]).toFixed(2) + "</li>";
    }).join("");
    body.innerHTML =
      '<p>宝妈指数基于公开论坛帖子的关键词分析，衡量散户（"小白"）讨论热度与情绪。' +
      "指数范围为 0–100，越高表示小白越活跃，市场情绪越可能处于危险区域。</p>" +
      "<p>公式版本：<code>" + escapeHtml(m.formula_version || "?") + "</code> · 线上定时任务只读取无需登录的公开页面；登录依赖型来源（小红书）默认为本地可选，公开部署中标记为不可用。</p>" +
      (wLines ? "<ul>" + wLines + "</ul>" : "") +
      '<p>历史数据若不足，会显示"暂无历史数据"，绝不编造曲线。过期/降级状态会以横幅标明。</p>';
    box.hidden = false;
  }

  function renderFooter(payload) {
    var src = $("footer-sources");
    if (!payload.sources || !payload.sources.length) {
      src.textContent = "数据来源：暂无可用数据源";
      return;
    }
    // Honest footer: only list sources actually in the payload, with their real mode.
    var parts = payload.sources.map(function (s) {
      var modeText = { live: "实时", simulated: "模拟", unavailable: "不可用" }[s.mode] || s.mode;
      return escapeHtml(s.label) + "（" + modeText + "）";
    });
    src.innerHTML = "数据来源：" + parts.join(" · ");
  }

  function renderEmpty(payload, clientStale) {
    // Insufficient-history / fully-empty state: clear charts + posts, keep status honest.
    renderStatus(payload, clientStale);
    renderUpdateTime(payload);
    $("cards").setAttribute("aria-busy", "false");
    $("cards").innerHTML = '<div class="state"><span class="icon">📭</span>暂无可用指数数据。<br>历史数据不足或所有数据源当前不可用，将在下次成功采集后更新。</div>';
    $("charts").innerHTML = '<div class="chart-box"><h3>历史趋势</h3><div class="chart-fallback"><p>暂无历史数据，将在采集到足够数据后显示趋势。</p></div></div>';
    var tp = $("top-posts");
    tp.innerHTML = '<h3>🔥 今日最"小白"的帖子</h3><div class="state">暂无数据。</div>';
    renderMethodology(payload);
    renderFooter(payload);
  }

  function renderError(err) {
    $("cards").setAttribute("aria-busy", "false");
    $("cards").innerHTML = '<div class="state"><span class="icon">⚠️</span>数据加载失败。<br>' +
      '<span class="post-meta">' + escapeHtml(err && err.message ? err.message : String(err)) + "</span><br>" +
      "请稍后重试，或直接查看 <a href=\"" + DATA_PATH + "\">原始数据 (JSON)</a>。</div>";
    $("charts").innerHTML = "";
    $("top-posts").innerHTML = '<h3>🔥 今日最"小白"的帖子</h3><div class="state">数据加载失败。</div>';
  }

  function render(payload) {
    var clientStale = computeClientStale(payload);
    var isEmpty = !payload.latest && (!payload.sector_history || Object.keys(payload.sector_history).every(function (k) { return !(payload.sector_history[k] && payload.sector_history[k].length); }));
    if (isEmpty) {
      renderEmpty(payload, clientStale);
      return;
    }
    renderStatus(payload, clientStale);
    renderUpdateTime(payload);
    renderCards(payload);
    renderCharts(payload);
    renderTopPosts(payload);
    renderMethodology(payload);
    renderFooter(payload);
  }

  function load() {
    fetch(DATA_PATH, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(render)
      .catch(function (e) {
        // If Chart.js failed to load earlier, still surface a usable shell.
        renderError(e);
        renderFooter({ sources: [] });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
