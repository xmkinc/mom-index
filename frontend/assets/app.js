/* 宝妈指数 dashboard app — schema v3 renderer with explicit v2 fallback
 * Handles: version gating, four separate evidence concerns, degraded/stale,
 * chart-failure fallback, client-side staleness, and honest source labels.
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
  /* Canonical backend reason-code vocabulary (mom_index/analysis/quality.py,
   * CANONICAL_REASON_CODES). tests/test_site_compatibility.py fails if any
   * canonical code is missing here. */
  var QUALITY_REASON_LABELS = {
    empty_sample: "本期没有可用的有效样本",
    sample_size_below_30: "有效样本少于 30 条（触发低置信度）",
    sample_size_below_60: "有效样本少于高置信门槛 60 条",
    title_only_ratio_above_0_8: "仅标题样本比例超过 80%（触发低置信度）",
    title_only_ratio_above_0_4: "仅标题样本比例高于高置信门槛 40%",
    classifier_evidence_coverage_below_0_3: "分类器证据覆盖率低于 30%（触发低置信度）",
    classifier_evidence_coverage_below_0_5: "分类器证据覆盖率低于高置信门槛 50%",
    known_in_window_ratio_below_0_6: "已知时间样本的观察窗口内比例低于 60%",
  };
  /* Quality-model versions whose gate semantics this renderer understands.
   * Unknown versions fall back to labeled reason codes. */
  var KNOWN_QUALITY_MODELS = { "1.0": true };
  /* Presentation metadata for numeric gates emitted by known models. */
  var QUALITY_GATE_TEXT = {
    sample_size_below_30: { metric: "有效样本", kind: "count" },
    sample_size_below_60: { metric: "有效样本", kind: "count" },
    title_only_ratio_above_0_8: { metric: "仅标题样本比例", kind: "ratio" },
    title_only_ratio_above_0_4: { metric: "仅标题样本比例", kind: "ratio" },
    classifier_evidence_coverage_below_0_3: { metric: "分类器证据覆盖率", kind: "ratio" },
    classifier_evidence_coverage_below_0_5: { metric: "分类器证据覆盖率", kind: "ratio" },
    known_in_window_ratio_below_0_6: { metric: "观察窗口内已知时间样本比例", kind: "ratio" },
  };

  function hasOwn(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj, String(key));
  }

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

  function finiteNumber(value) {
    if (value == null || value === "" || typeof value === "boolean") return null;
    var n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function numberText(value, digits, fallback) {
    var n = finiteNumber(value);
    return n == null ? (fallback || "—") : n.toFixed(digits == null ? 0 : digits);
  }

  function ratioPercent(value) {
    var n = finiteNumber(value);
    return n == null ? "—" : (n * 100).toFixed(0) + "%";
  }

  function safeExternalUrl(value) {
    if (!value) return "";
    try {
      var parsed = new URL(String(value), window.location.href);
      return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : "";
    } catch (e) {
      return "";
    }
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
    var allowedModes = { live: true, imported: true, simulated: true, unavailable: true };
    var mode = allowedModes[src.mode] ? src.mode : "unavailable";
    var label = src.label || src.id || "";
    var modeText = { live: "实时", imported: "本地清洗导入", simulated: "模拟", unavailable: "不可用" }[mode];
    return '<span class="badge ' + mode + '" title="' + escapeHtml(label) + " · " + modeText +
      '"><span class="dot"></span>' + escapeHtml(label) + " · " + modeText + "</span>";
  }

  function renderStatus(payload, clientStale, version) {
    var bar = $("status-bar");
    var parts = [];

    var isStale = (payload.freshness && payload.freshness.is_stale) || clientStale.stale;
    var lastSuccess = payload.freshness && payload.freshness.last_success_at;

    if (version === 2) {
      parts.push('<div class="banner legacy"><strong>旧版数据（schema v2）</strong>：可继续查看社交指数与语言证据；样本质量和市场背景在此版本中不可用，旧版解释文本不展示。</div>');
    }

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
    if (d.buy_sell_ratio == null) return "∞";
    return numberText(d.buy_sell_ratio, 2);
  }

  function concernPanel(number, title, note, className, body) {
    return '<section class="concern-panel ' + className + '">' +
      '<div class="concern-heading"><span class="concern-number">' + number + "</span><div><h2>" +
      title + '</h2><p>' + note + "</p></div></div>" + body + "</section>";
  }

  function unavailableGrid(message) {
    return '<div class="panel-grid"><div class="state panel-state"><span class="icon">📭</span>' +
      escapeHtml(message) + "</div></div>";
  }

  function renderSocialIndex(payload, version) {
    var sectors = payload.latest && payload.latest.sectors;
    var body;
    if (!sectors) {
      body = unavailableGrid("暂无可用社交指数；历史不足或来源当前不可用。");
    } else {
      body = '<div class="panel-grid">' + Object.keys(SECTOR_NAMES).map(function (key) {
        var sector = sectors[key] || {};
        var interpretation = version === 3
          ? (sector.interpretation || "暂无分类解释。")
          : "旧版解释文本已隐藏，仅保留历史指数数值。";
        return '<article class="card ' + key + '">' +
          '<div class="sector-name">' + SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] + "</div>" +
          '<div class="index-value">' + numberText(sector.index, 0) + "</div>" +
          '<div class="index-label">社交讨论指数（0–100）</div>' +
          '<div class="signal ' + signalClass(finiteNumber(sector.index)) + '">' + escapeHtml(interpretation) + "</div>" +
        "</article>";
      }).join("") + "</div>";
    }
    return concernPanel(
      "1",
      "社交指数",
      "仅由公开讨论样本的确定性分类结果计算，不使用市场行情。",
      "social-concern",
      body
    );
  }

  function renderActionEvidence(payload) {
    var sectors = payload.latest && payload.latest.sectors;
    var body;
    if (!sectors) {
      body = unavailableGrid("暂无可用的买卖语言分类证据。");
    } else {
      body = '<div class="panel-grid">' + Object.keys(SECTOR_NAMES).map(function (key) {
        var details = (sectors[key] && sectors[key].details) || {};
        var buyCount = finiteNumber(details.buy_count);
        var sellCount = finiteNumber(details.sell_count);
        buyCount = buyCount == null ? 0 : Math.max(0, buyCount);
        sellCount = sellCount == null ? 0 : Math.max(0, sellCount);
        var languageTotal = buyCount + sellCount;
        var buyPct = languageTotal ? Math.min(100, Math.max(0, (buyCount / languageTotal) * 100)) : 0;
        return '<article class="card ' + key + '">' +
          '<div class="sector-name">' + SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] + "</div>" +
          '<div class="sub-index">' +
            '<div class="buy"><div class="num">' + numberText(details.mom_buy_index, 0, "0") + '</div><div class="lbl">买入语言指数</div></div>' +
            '<div class="sell"><div class="num">' + numberText(details.mom_sell_index, 0, "0") + '</div><div class="lbl">卖出语言指数</div></div>' +
          "</div>" +
          '<div class="ratio-row" aria-label="买卖语言样本计数">' +
            "<span>卖出语言 " + numberText(sellCount, 0, "0") + '</span><div class="bar"><div style="width:' + buyPct.toFixed(2) + '%"></div></div><span>买入语言 ' + numberText(buyCount, 0, "0") + "</span>" +
          "</div>" +
          '<div class="detail-row"><span>语言计数比（买/卖）</span><span>' + escapeHtml(buySellRatioText(details)) + "</span></div>" +
          '<div class="detail-row"><span>新手语言样本</span><span>' +
            numberText(details.newbie_posts, 0, "0") + "/" + numberText(details.valid_posts != null ? details.valid_posts : details.total_posts, 0, "0") +
            "（" + numberText(details.newbie_ratio, 0, "0") + "%）</span></div>" +
          '<div class="detail-row"><span>样本平均情绪值</span><span>' + numberText(details.avg_sentiment, 0) + "</span></div>" +
        "</article>";
      }).join("") + "</div>";
    }
    return concernPanel(
      "2",
      "买卖语言证据",
      "展示分类器识别出的语言倾向，不代表真实持仓、交易行为或未来方向。",
      "evidence-concern",
      body
    );
  }

  function platformCountsHtml(platformCounts) {
    if (!platformCounts || typeof platformCounts !== "object") return "—";
    var labels = { guba: "股吧", xiaohongshu: "小红书" };
    var keys = Object.keys(platformCounts).sort();
    if (!keys.length) return "—";
    return keys.map(function (key) {
      return escapeHtml(labels[key] || key) + " " + numberText(platformCounts[key], 0, "0");
    }).join(" · ");
  }

  function reasonLineHtml(code) {
    var rawCode = String(code);
    var label = hasOwn(QUALITY_REASON_LABELS, rawCode) ? QUALITY_REASON_LABELS[rawCode] : rawCode;
    return '<li class="quality-reason">' + escapeHtml(label) +
      (label === rawCode ? "" : ' <code>' + escapeHtml(rawCode) + "</code>") + "</li>";
  }

  function qualityReasonsHtml(reasonCodes) {
    if (!Array.isArray(reasonCodes) || !reasonCodes.length) {
      return '<li class="quality-reason met">未记录未通过的质量门槛</li>';
    }
    return reasonCodes.map(reasonLineHtml).join("");
  }

  /* Validate the optional machine-readable gate list; unusable lists are
   * ignored entirely so the reason-code fallback still renders. */
  function validGates(gates) {
    if (!Array.isArray(gates) || gates.length > 12) return null;
    for (var i = 0; i < gates.length; i++) {
      var g = gates[i];
      if (!g || typeof g !== "object" || Array.isArray(g)) return null;
      if (typeof g.code !== "string" || !g.code) return null;
      if (g.level !== "low" && g.level !== "high") return null;
      if (typeof g.passed !== "boolean") return null;
      if (typeof g.actual !== "number" || !Number.isFinite(g.actual) || g.actual < 0) return null;
      if (typeof g.threshold !== "number" || !Number.isFinite(g.threshold) || g.threshold < 0) return null;
      if (g.comparator !== "gte" && g.comparator !== "lte") return null;
    }
    return gates;
  }

  function gateRatioText(value) {
    var n = finiteNumber(value);
    if (n == null) return "—";
    var pct = n * 100;
    var rounded = Math.round(pct);
    return (Math.abs(pct - rounded) < 1e-9 ? String(rounded) : pct.toFixed(1)) + "%";
  }

  function gateLineHtml(g) {
    var comparatorSymbol = g.comparator === "lte" ? "≤" : "≥";
    var levelText = g.level === "low" ? "（触发低置信度）" : "（未达到高置信门槛）";
    if (!hasOwn(QUALITY_GATE_TEXT, g.code)) {
      // Unknown gate codes stay visible with their raw evidence.
      return '<li class="quality-reason"><code>' + escapeHtml(g.code) + "</code> 实际 " +
        escapeHtml(String(g.actual)) + "，要求 " + comparatorSymbol + " " +
        escapeHtml(String(g.threshold)) + levelText + "</li>";
    }
    var meta = QUALITY_GATE_TEXT[g.code];
    var actualText = meta.kind === "ratio" ? gateRatioText(g.actual) : numberText(g.actual, 0, "0") + " 条";
    var thresholdText = meta.kind === "ratio" ? gateRatioText(g.threshold) : numberText(g.threshold, 0, "0") + " 条";
    return '<li class="quality-reason">' + meta.metric + " " + actualText +
      "，未满足 " + comparatorSymbol + " " + thresholdText + " 的要求" + levelText + "</li>";
  }

  /* Short evidence-availability note built only from public payload
   * aggregates; it describes sample coverage, never inferred causes. */
  function evidenceNoteHtml(quality) {
    var parts = [
      "样本分布 " + platformCountsHtml(quality.platform_counts),
      "仅标题可分析 " + ratioPercent(quality.title_only_ratio),
      "发布时间未知 " + ratioPercent(quality.unknown_time_ratio),
    ];
    return '<li class="quality-reason met">证据说明：' + parts.join("，") +
      "。以上只描述样本覆盖与时效，不推断原因。</li>";
  }

  function qualityExplanationHtml(quality) {
    var items;
    var gates = hasOwn(KNOWN_QUALITY_MODELS, quality.model_version)
      ? validGates(quality.gates)
      : null;
    if (gates) {
      var gateCodes = {};
      gates.forEach(function (g) { gateCodes[g.code] = true; });
      // Canonical codes without a numeric gate (e.g. empty_sample) still
      // surface through their reason-code label.
      var extraReasons = (Array.isArray(quality.reason_codes) ? quality.reason_codes : [])
        .filter(function (code) { return !hasOwn(gateCodes, code); });
      var failed = gates.filter(function (g) { return !g.passed; });
      items = extraReasons.map(reasonLineHtml).join("") + failed.map(gateLineHtml).join("");
      if (!items) items = '<li class="quality-reason met">全部质量门槛均已通过</li>';
    } else {
      items = qualityReasonsHtml(quality.reason_codes);
    }
    return '<div class="quality-reasons quality-explanation"><div class="mini-heading">质量门槛说明</div><ul>' +
      items + evidenceNoteHtml(quality) + "</ul></div>";
  }

  function renderSampleQuality(payload, version) {
    var sectors = payload.latest && payload.latest.sectors;
    var body;
    if (version === 2) {
      body = unavailableGrid("schema v2 不包含客观样本质量字段。");
    } else if (!sectors) {
      body = unavailableGrid("当前没有社交读数，因此无法展示样本质量。");
    } else {
      body = '<div class="panel-grid">' + Object.keys(SECTOR_NAMES).map(function (key) {
        var quality = sectors[key] && sectors[key].sample_quality;
        if (!quality) {
          return '<article class="card ' + key + ' quality-card"><div class="sector-name">' +
            SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] +
            '</div><div class="state compact-state">该读数来自旧版历史，未记录样本质量。</div></article>';
        }
        var allowedConfidence = { high: true, medium: true, low: true };
        var confidence = allowedConfidence[quality.confidence] ? quality.confidence : "unknown";
        var confidenceLabel = { high: "高", medium: "中", low: "低", unknown: "未知" }[confidence];
        return '<article class="card ' + key + ' quality-card">' +
          '<div class="sector-name">' + SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] +
            '<span class="confidence ' + confidence + '">' + confidenceLabel + "置信度</span></div>" +
          '<dl class="quality-metrics">' +
            '<div><dt>有效样本</dt><dd>' + numberText(quality.valid_sample_size, 0, "0") + " 条</dd></div>" +
            '<div><dt>仅标题比例</dt><dd>' + ratioPercent(quality.title_only_ratio) + "</dd></div>" +
            '<div><dt>分类证据覆盖</dt><dd>' + ratioPercent(quality.classifier_evidence_coverage) + "</dd></div>" +
            '<div><dt>已知时间且在窗口内</dt><dd>' + ratioPercent(quality.known_in_window_ratio) + "</dd></div>" +
            '<div><dt>未知发布时间</dt><dd>' + ratioPercent(quality.unknown_time_ratio) + "</dd></div>" +
            '<div><dt>观察窗口</dt><dd>' + numberText(quality.window_hours, 0) + " 小时</dd></div>" +
            '<div class="wide"><dt>平台样本</dt><dd>' + platformCountsHtml(quality.platform_counts) + "</dd></div>" +
          "</dl>" +
          qualityExplanationHtml(quality) +
          '<div class="model-version">质量模型 ' + escapeHtml(quality.model_version || "—") + "</div>" +
        "</article>";
      }).join("") + "</div>";
    }
    return concernPanel(
      "3",
      "客观样本质量",
      "置信度只描述样本覆盖与时效，不提高或降低社交指数。",
      "quality-concern",
      body
    );
  }

  function marketReturnHtml(returns, windowName) {
    var value = returns && finiteNumber(returns[windowName]);
    if (value == null) return '<span class="market-return unavailable">—</span>';
    var cls = value > 0 ? "positive" : (value < 0 ? "negative" : "flat");
    var prefix = value > 0 ? "+" : "";
    return '<span class="market-return ' + cls + '">' + prefix + value.toFixed(2) + "%</span>";
  }

  function renderMarketContext(payload, version) {
    var market = payload.market_context;
    var body;
    if (version === 2) {
      body = unavailableGrid("schema v2 不包含独立市场背景。");
    } else if (!market || market.status === "unavailable") {
      var errors = market && Array.isArray(market.errors) ? market.errors : [];
      body = unavailableGrid(errors.length ? errors.join("；") : "市场背景当前不可用；社交指数仍按独立公式展示。");
    } else {
      var status = market.status === "available" ? "available" : "degraded";
      var statusLabel = status === "available" ? "完整" : "部分可用";
      var provider = market.provider || "未标注来源";
      var importedAt = formatShanghaiTime(market.imported_at);
      var sectors = market.sectors || {};
      body = '<div class="market-provenance ' + status + '"><span>状态：' + statusLabel +
        "</span><span>来源：" + escapeHtml(provider) + "</span><span>导入：" + escapeHtml(importedAt) + "</span></div>" +
        '<div class="panel-grid">' + Object.keys(SECTOR_NAMES).map(function (key) {
          var item = sectors[key];
          if (!item) {
            return '<article class="card ' + key + ' market-card"><div class="sector-name">' +
              SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] +
              '</div><div class="state compact-state">该板块行情背景不可用。</div></article>';
          }
          return '<article class="card ' + key + ' market-card">' +
            '<div class="sector-name">' + SECTOR_EMOJI[key] + " " + SECTOR_NAMES[key] + "</div>" +
            '<div class="market-reference"><strong>' + escapeHtml(item.name || "—") + "</strong><code>" +
              escapeHtml(item.symbol || "—") + "</code></div>" +
            '<div class="market-returns">' +
              '<div><span>1 日</span>' + marketReturnHtml(item.returns, "1d") + "</div>" +
              '<div><span>5 日</span>' + marketReturnHtml(item.returns, "5d") + "</div>" +
              '<div><span>20 日</span>' + marketReturnHtml(item.returns, "20d") + "</div>" +
            "</div>" +
            '<div class="market-asof">行情截至 ' + escapeHtml(formatShanghaiTime(item.as_of)) + "</div>" +
          "</article>";
        }).join("") + "</div>";
      if (Array.isArray(market.errors) && market.errors.length) {
        body += '<ul class="market-errors">' + market.errors.map(function (error) {
          return "<li>" + escapeHtml(error) + "</li>";
        }).join("") + "</ul>";
      }
    }
    return concernPanel(
      "4",
      "独立市场背景",
      "参考标的收益仅作同期背景，不参与指数计算，也不解释二者关系。",
      "market-concern",
      body
    );
  }

  function renderCards(payload, version) {
    var container = $("cards");
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      renderSocialIndex(payload, version) +
      renderActionEvidence(payload) +
      renderSampleQuality(payload, version) +
      renderMarketContext(payload, version);
  }

  function chartFallback(sector, records) {
    // Rendered when Chart.js is unavailable or fails. Honest, no invented curves.
    if (!records || !records.length) {
      return '<div class="chart-fallback"><p>暂无历史数据。</p></div>';
    }
    var rows = records.slice().reverse().map(function (r) {
      var mode = { live: "live", imported: "imported", simulated: "simulated" }[r.source_mode] || "simulated";
      var modeText = { live: "实时", imported: "导入", simulated: "模拟" }[mode];
      return "<tr><td>" + escapeHtml(r.date) + "</td><td class=\"num\">" + Number(r.index).toFixed(0) +
        '</td><td><span class="badge ' + mode + '" style="font-size:10px">' +
        modeText + "</span></td></tr>";
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
    Object.keys(SECTOR_NAMES).forEach(function (key) {
      var sector = latest.sectors[key];
      var posts = (sector && sector.top_newbie_posts) || [];
      posts.forEach(function (p) {
        var safeIntent = { buy: "buy", sell: "sell", neutral: "neutral" }[p.intent] || "neutral";
        allTop.push({
          title: p.title || "",
          score: finiteNumber(p.score) == null ? 0 : finiteNumber(p.score),
          level: p.level || "",
          reasoning: p.reasoning || "",
          intent: safeIntent,
          key_signals: p.key_signals || [],
          source_url: safeExternalUrl(p.source_url),
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
        var intentMap = { buy: "买入语言", sell: "卖出语言", neutral: "中性语言" };
        var intentTxt = intentMap[p.intent];
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
    var heading = "<h3>🔎 典型分类证据帖子</h3>";
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
      "指数范围为 0–100，数值只描述分类器在当前样本中识别到的新手语言集中程度，不代表市场方向、因果关系或预测。</p>" +
      "<p>公式版本：<code>" + escapeHtml(m.formula_version || "?") + "</code>" +
      (m.confidence_model_version ? " · 样本质量模型：<code>" + escapeHtml(m.confidence_model_version) + "</code>" : "") +
      " · 线上定时任务只读取无需登录的公开页面；小红书只允许本地清洗后显式导入，公开部署不会登录采集。</p>" +
      (wLines ? "<ul>" + wLines + "</ul>" : "") +
      '<p>买卖语言、样本质量和市场背景分别展示；市场背景不进入指数公式。历史不足时不编造曲线，过期或降级状态会明确标注。</p>';
    box.hidden = false;
  }

  function renderFooter(payload, version) {
    var src = $("footer-sources");
    var schema = $("footer-schema");
    if (schema) schema.textContent = version === 2 ? "schema v2（旧版兼容）" : (version === 3 ? "schema v3" : "未知 schema");
    if (!payload.sources || !payload.sources.length) {
      src.textContent = "数据来源：暂无可用数据源";
      return;
    }
    // Honest footer: only list sources actually in the payload, with their real mode.
    var parts = payload.sources.map(function (s) {
      var modeText = { live: "实时", imported: "本地清洗导入", simulated: "模拟", unavailable: "不可用" }[s.mode] || "状态未知";
      return escapeHtml(s.label) + "（" + modeText + "）";
    });
    src.innerHTML = "数据来源：" + parts.join(" · ");
  }

  function renderEmpty(payload, clientStale, version) {
    // Insufficient-history / fully-empty state: clear charts + posts, keep status honest.
    renderStatus(payload, clientStale, version);
    renderUpdateTime(payload);
    renderCards(payload, version);
    $("charts").innerHTML = '<div class="chart-box"><h3>历史趋势</h3><div class="chart-fallback"><p>暂无历史数据，将在采集到足够数据后显示趋势。</p></div></div>';
    var tp = $("top-posts");
    tp.innerHTML = '<h3>🔎 典型分类证据帖子</h3><div class="state">暂无数据。</div>';
    renderMethodology(payload);
    renderFooter(payload, version);
  }

  function renderError(err) {
    $("status-bar").innerHTML = '<div class="banner error">无法读取公开面板数据。</div>';
    $("cards").setAttribute("aria-busy", "false");
    $("cards").innerHTML = '<div class="state"><span class="icon">⚠️</span>数据加载失败。<br>' +
      '<span class="post-meta">' + escapeHtml(err && err.message ? err.message : String(err)) + "</span><br>" +
      "请稍后重试，或直接查看 <a href=\"" + DATA_PATH + "\">原始数据 (JSON)</a>。</div>";
    $("charts").innerHTML = "";
    $("top-posts").innerHTML = '<h3>🔎 典型分类证据帖子</h3><div class="state">数据加载失败。</div>';
    $("methodology").hidden = true;
  }

  function renderUnsupportedVersion(version) {
    var shownVersion = version == null ? "缺失" : String(version);
    $("status-bar").innerHTML = '<div class="banner error"><strong>不支持的数据版本</strong>：收到 schema ' +
      escapeHtml(shownVersion) + "，本页面只支持 v3，并为 v2 提供只读兼容显示。</div>";
    $("update-time").textContent = "数据未渲染：schema 版本不受支持";
    $("cards").setAttribute("aria-busy", "false");
    $("cards").innerHTML = '<div class="state"><span class="icon">⛔</span>已停止渲染未知版本，避免误读字段含义。<br>' +
      '可直接检查 <a href="' + DATA_PATH + '">原始数据 (JSON)</a>。</div>';
    $("charts").innerHTML = "";
    $("top-posts").innerHTML = '<h3>🔎 典型分类证据帖子</h3><div class="state">未知版本未渲染。</div>';
    $("methodology").hidden = true;
    renderFooter({ sources: [] }, null);
  }

  function render(payload) {
    if (!payload || typeof payload !== "object") {
      renderUnsupportedVersion(null);
      return;
    }
    var version = payload.schema_version;
    if (version !== 2 && version !== 3) {
      renderUnsupportedVersion(version);
      return;
    }
    var clientStale = computeClientStale(payload);
    var isEmpty = !payload.latest && (!payload.sector_history || Object.keys(payload.sector_history).every(function (k) { return !(payload.sector_history[k] && payload.sector_history[k].length); }));
    if (isEmpty) {
      renderEmpty(payload, clientStale, version);
      return;
    }
    renderStatus(payload, clientStale, version);
    renderUpdateTime(payload);
    renderCards(payload, version);
    renderCharts(payload);
    renderTopPosts(payload);
    renderMethodology(payload);
    renderFooter(payload, version);
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
        renderFooter({ sources: [] }, null);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
