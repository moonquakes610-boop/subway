/**
 * 地铁出行指南 — 综合页（需先通过 __appBoot 鉴权）
 * 与后端同域使用 Cookie 会话，fetch 需 credentials: 'include'（由 apiFetch 处理）
 */
(function () {
  var API_CANDIDATES = [
    "",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://127.0.0.1:8777",
    "http://localhost:8777",
  ];

  var apiBaseReady = false;
  var API_BASE = "";

  function $(id) {
    return document.getElementById(id);
  }

  function updateApiBaseDisplay() {
    var el = $("apiBaseDisplay");
    if (el) el.textContent = API_BASE || location.origin;
  }

  function probeApiBase(base) {
    var p = (base || "").replace(/\/$/, "");
    return fetch(p + "/api/health", { credentials: "include" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        return !!(d && d.ok);
      })
      .catch(function () {
        return false;
      });
  }

  function ensureApiBase() {
    if (apiBaseReady) {
      window.SUBWAY_API = API_BASE || "";
      updateApiBaseDisplay();
      return Promise.resolve(API_BASE);
    }
    if (window.getApiBase && window.getApiBase() !== "") {
      API_BASE = window.getApiBase();
      window.SUBWAY_API = API_BASE || "";
      apiBaseReady = true;
      updateApiBaseDisplay();
      return Promise.resolve(API_BASE);
    }
    var i = 0;
    function tryNext() {
      if (i >= API_CANDIDATES.length) {
        API_BASE = "";
        window.SUBWAY_API = API_BASE || "";
        apiBaseReady = true;
        updateApiBaseDisplay();
        return Promise.resolve(API_BASE);
      }
      var b = API_CANDIDATES[i++];
      return probeApiBase(b).then(function (ok) {
        if (ok) {
          API_BASE = b;
          window.SUBWAY_API = API_BASE || "";
          apiBaseReady = true;
          updateApiBaseDisplay();
          return API_BASE;
        }
        return tryNext();
      });
    }
    return tryNext();
  }

  function apiUrl(path) {
    var p = path.charAt(0) === "/" ? path : "/" + path;
    return (API_BASE || "") + p;
  }

  function jsonFetch(path, init) {
    init = init || {};
    init.credentials = "include";
    return window.apiFetch(path, init).then(function (r) {
      if (r.status === 401) {
        location.replace("/login.html?next=" + encodeURIComponent("/app.html"));
        return Promise.reject(new Error("需要登录"));
      }
      return r;
    });
  }

  // ----- 主逻辑在 main 内注册 -----

  function main(boot) {
    if (!boot || !boot.ok) {
      return;
    }
    if (boot.user) {
      var nu = $("navUser");
      var na = $("navAvatar");
      if (nu) {
        nu.textContent = boot.user.username || "";
      }
      if (na) {
        na.textContent = boot.user.avatar || "🙂";
      }
      var adminLink = $("navAdminLink");
      if (adminLink && !boot.user.is_admin) {
        adminLink.style.display = "none";
      }
    }
    var lo = $("navLogout");
    if (lo) {
      lo.addEventListener("click", function () {
        jsonFetch("/api/auth/logout", { method: "POST" })
          .then(function () {
            return null;
          })
          .catch(function () {
            return null;
          })
          .then(function () {
            location.assign("/");
          });
      });
    }

    var elFrom = $("from");
    var elTo = $("to");
    var elGuideMode = $("guideMode");
    var elStrategy = function (name) {
      return document.querySelector('input[name="strategy"][value="' + name + '"]');
    };
    var btn = $("queryBtn");
    var statusEl = $("status");
    var resultSection = $("resultSection");
    var emptyHint = $("emptyHint");
    var elQueryTime = $("queryTime");
    var metricTime = $("metricTime");
    var metricArrival = $("metricArrival");
    var metricFare = $("metricFare");
    var metricXfer = $("metricXfer");
    var metricLinePlan = $("metricLinePlan");
    var metricTransferPlan = $("metricTransferPlan");
    var metricServiceCheck = $("metricServiceCheck");
    var routeTransitRoot = $("routeTransitRoot");
    var routeOpStatusPanel = $("routeOpStatusPanel");
    var opQueryTimeLine = $("opQueryTimeLine");
    var opHeadline = $("opHeadline");
    var opServiceTable = $("opServiceTable");
    var opRuntimeSubtitle = $("opRuntimeSubtitle");
    var opRuntimeNote = $("opRuntimeNote");
    var opRuntimeList = $("opRuntimeList");
    var guideText = $("guideText");
    var copyGuideBtn = $("copyGuideBtn");
    var exportGuideBtn = $("exportGuideBtn");
    var alternativesGrid = $("alternativesGrid");
    var recommendReason = $("recommendReason");
    var sceneFocusPanel = $("sceneFocusPanel");
    var fbIssueType = $("fbIssueType");
    var fbSeverity = $("fbSeverity");
    var fbContact = $("fbContact");
    var fbRepro = $("fbRepro");
    var fbContent = $("fbContent");
    var fbSubmitBtn = $("fbSubmitBtn");
    var fbStatus = $("fbStatus");
    var lastQueryContext = null;
    var lastPlanPayload = null;
    var currentGuideMode = "commute";
    var resultA11yList = $("resultA11yList");
    var a11yResultStatus = $("a11yResultStatus");
    var rulesLoadStatus = $("rulesLoadStatus");
    var prohibitedLoadStatus = $("prohibitedLoadStatus");
    var a11yMeta = $("a11yMeta");

    var ICON_MAP = {
      local_fire_department: "🔥",
      gavel: "⚖",
      science: "🧪",
      wc: "🚻",
    };

    var MODE_LABELS = {
      commute: "通勤",
      tour: "游客",
      senior: "老人/带娃",
      rush: "赶时间",
    };

    var MODE_FOCUS = {
      commute: ["service_center", "blind_path", "accessibility_elevator"],
      tour: ["service_center", "accessibility_toilet", "blind_path"],
      senior: ["accessibility_elevator", "ramp", "accessibility_toilet", "service_center"],
      rush: ["accessibility_elevator", "service_center", "ramp"],
    };

    var FIELD_LABELS = {
      accessibility_elevator: "无障碍电梯",
      accessibility_toilet: "无障碍卫生间",
      ramp: "坡道",
      blind_path: "盲道",
      service_center: "客服中心位置",
      remark: "备注",
    };

    var MODE_PROFILE = {
      commute: {
        title: "通勤场景重点",
        concerns: ["准点到达", "换乘稳定性", "进出站效率"],
        tips: "优先关注预计到达时刻、换乘次数与客服位置，方便异常时快速处理。",
      },
      tour: {
        title: "游客场景重点",
        concerns: ["路线清晰易懂", "站内导引友好", "卫生间与客服可达性"],
        tips: "优先关注客服中心、卫生间和盲道信息，减少陌生站点迷路成本。",
      },
      senior: {
        title: "老人/带娃场景重点",
        concerns: ["少走楼梯", "步行负担低", "求助便利"],
        tips: "优先关注电梯、坡道、无障碍卫生间与客服中心，减少长距离换乘负担。",
      },
      rush: {
        title: "赶时间场景重点",
        concerns: ["最快到达", "减少等待", "快速求助通道"],
        tips: "优先关注最短时间方案、换乘次数与最近客服点，缩短临场决策时间。",
      },
    };

    function setStatus(type, text) {
      statusEl.className = "status " + (type || "");
      statusEl.textContent = text || "";
    }

    function showLoading(loading) {
      btn.disabled = loading;
    }

    function formatMinutes(n) {
      if (n == null || isNaN(n)) {
        return "—";
      }
      var s = String(n);
      if (s.endsWith(".0") || s.endsWith(".00")) {
        return String(parseFloat(n).toFixed(0));
      }
      return s;
    }

    function parseHhmmToMinutes(s) {
      if (!s) {
        return null;
      }
      var p = String(s).trim().split(":");
      if (p.length < 2) {
        return null;
      }
      var h = parseInt(p[0], 10);
      var m = parseInt(p[1], 10);
      if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) {
        return null;
      }
      return h * 60 + m;
    }

    function formatMinutesToHhmm(total) {
      var t = Math.floor(total);
      var day = "";
      if (t >= 24 * 60) {
        t = t % (24 * 60);
        day = "（次日）";
      }
      if (t < 0) {
        t += 24 * 60;
      }
      var h = Math.floor(t / 60);
      var m = t % 60;
      return (
        (h < 10 ? "0" : "") +
        h +
        ":" +
        (m < 10 ? "0" : "") +
        m +
        day
      );
    }

    function computeArrivalHhmm(queryHhmm, durationMin) {
      var base = parseHhmmToMinutes(queryHhmm);
      if (base == null || durationMin == null || isNaN(durationMin)) {
        return "—";
      }
      return formatMinutesToHhmm(base + Math.round(parseFloat(String(durationMin))));
    }

    function uniqueRouteLineNames(steps) {
      var o = [];
      var se = {};
      for (var i = 0; i < (steps || []).length; i++) {
        var ln = (steps[i] && steps[i].line) || "";
        if (ln && !se[ln]) {
          se[ln] = 1;
          o.push(ln);
        }
      }
      return o;
    }

    function runtimeLineMatchesRoute(rtLine, routeNames) {
      var R = rtLine || "";
      for (var i = 0; i < routeNames.length; i++) {
        var q = routeNames[i] || "";
        if (q === R) {
          return true;
        }
        if (q && R && (R.indexOf(q) >= 0 || q.indexOf(R) >= 0)) {
          return true;
        }
      }
      return false;
    }

    function renderTransitRoute(steps) {
      if (!routeTransitRoot) {
        return;
      }
      routeTransitRoot.innerHTML = "";
      if (!steps || !steps.length) {
        return;
      }
      var legs = [];
      var cur = null;
      for (var i = 0; i < steps.length; i++) {
        var row = steps[i];
        var line = row.line || "—";
        var st = row.station || "—";
        if (!cur || cur.line !== line) {
          if (cur) {
            legs.push(cur);
          }
          cur = { line: line, stations: [st] };
        } else {
          cur.stations.push(st);
        }
      }
      if (cur) {
        legs.push(cur);
      }
      for (var j = 0; j < legs.length; j++) {
        var leg = legs[j];
        var legEl = document.createElement("div");
        legEl.className = "transit-leg";
        var head = document.createElement("div");
        head.className = "transit-leg__head";
        var badge = document.createElement("span");
        badge.className = "transit-line-badge";
        badge.textContent = leg.line;
        head.appendChild(badge);
        legEl.appendChild(head);
        var strip = document.createElement("div");
        strip.className = "transit-station-strip";
        for (var k = 0; k < leg.stations.length; k++) {
          if (k > 0) {
            var ar = document.createElement("span");
            ar.className = "transit-arrow";
            ar.setAttribute("aria-hidden", "true");
            ar.textContent = " → ";
            strip.appendChild(ar);
          }
          var sp = document.createElement("span");
          sp.className = "transit-station";
          sp.textContent = leg.stations[k];
          strip.appendChild(sp);
        }
        legEl.appendChild(strip);
        routeTransitRoot.appendChild(legEl);
      }
    }

    function fillOpServiceTable(container, lines) {
      if (!container) {
        return;
      }
      container.innerHTML = "";
      if (!lines || !lines.length) {
        var p = document.createElement("p");
        p.className = "section-lead";
        p.textContent = "未返回首末班明细。";
        container.appendChild(p);
        return;
      }
      var t = document.createElement("table");
      t.className = "data-table";
      t.innerHTML =
        "<thead><tr><th>线路</th><th>约首班</th><th>约末班服务结束</th><th>当前查询时刻是否在窗内（模型）</th></tr></thead>";
      var tb = document.createElement("tbody");
      for (var i = 0; i < lines.length; i++) {
        var row = lines[i] || {};
        var tr = document.createElement("tr");
        var ins = row.in_service_at_query;
        if (ins === false) {
          tr.className = "op-row--closed";
        }
        function td(txt) {
          var c = document.createElement("td");
          c.textContent = txt != null ? String(txt) : "—";
          return c;
        }
        tr.appendChild(td(row.line));
        tr.appendChild(td(row.first_hhmm));
        tr.appendChild(td(row.last_hhmm));
        var mark = ins === true ? "是" : ins === false ? "否（红字提醒）" : "—";
        tr.appendChild(td(mark));
        tb.appendChild(tr);
      }
      t.appendChild(tb);
      container.appendChild(t);
    }

    function renderRouteOpPanel(data, steps) {
      if (!routeOpStatusPanel) {
        return;
      }
      var svc = data && data.service_time_check;
      var qh = (svc && svc.query_hhmm) || "";
      if (opQueryTimeLine) {
        opQueryTimeLine.textContent = "查询/假设出发时刻：" + (qh || "（与服务器一致）");
      }
      if (opHeadline) {
        opHeadline.textContent = (svc && svc.headline) || (svc && svc.message) || "";
      }
      fillOpServiceTable(opServiceTable, (svc && svc.lines) || []);
      routeOpStatusPanel.classList.remove("hidden");
      var routeLineNames = uniqueRouteLineNames(steps);
      if (opRuntimeSubtitle) {
        opRuntimeSubtitle.textContent = "本路线所涉线路的客流/运营提示（仅显示与本次路线相关的条目）";
      }
      if (opRuntimeNote) {
        opRuntimeNote.textContent = "正在加载运营提示…";
      }
      if (opRuntimeList) {
        opRuntimeList.innerHTML = "";
      }
      jsonFetch("/api/runtime/status")
        .then(function (r) {
          return r.json();
        })
        .then(function (d) {
          if (!d || !d.ok || !d.data) {
            if (opRuntimeNote) {
              opRuntimeNote.textContent = "运营提示加载失败。";
            }
            return;
          }
          var rt = d.data;
          var items = (rt && rt.lines) || [];
          var fil = [];
          for (var i = 0; i < items.length; i++) {
            if (runtimeLineMatchesRoute(items[i].line, routeLineNames)) {
              fil.push(items[i]);
            }
          }
          if (opRuntimeNote) {
            opRuntimeNote.textContent =
              (rt.summary || "请关注车站广播与官方 App。") +
              (rt.updated_at ? "（数据更新时间：" + rt.updated_at + "）" : "");
          }
          if (!opRuntimeList) {
            return;
          }
          opRuntimeList.innerHTML = "";
          if (!fil.length) {
            var none = document.createElement("div");
            none.className = "runtime-item";
            none.textContent =
              "当前数据中暂无与本次路线完全匹配的线路提示，请以现场公告为准。";
            opRuntimeList.appendChild(none);
            return;
          }
          for (var j = 0; j < fil.length; j++) {
            var item = fil[j];
            var el = document.createElement("div");
            var st = item.status || "normal";
            el.className = "runtime-item runtime-item--" + st;
            el.textContent = (item.line || "线路") + "：" + (item.message || "");
            opRuntimeList.appendChild(el);
          }
        })
        .catch(function () {
          if (opRuntimeNote) {
            opRuntimeNote.textContent = "运营提示加载失败。";
          }
        });
    }

    function buildLineAndTransferSummary(steps) {
      if (!steps || !steps.length) {
        return { lines: "—", transfers: "—" };
      }
      var lines = [];
      var transferStations = [];
      for (var i = 0; i < steps.length; i++) {
        var ln = steps[i].line || "";
        if (ln && lines.indexOf(ln) < 0) lines.push(ln);
        if (i > 0 && steps[i - 1].line !== steps[i].line) {
          transferStations.push(steps[i].station || "");
        }
      }
      return {
        lines: lines.length ? lines.join(" → ") : "—",
        transfers: transferStations.length ? transferStations.join("、") : "无需换乘",
      };
    }

    function buildRecommendationFallback(data) {
      if (data && data.recommendation_reason) return data.recommendation_reason;
      var alts = (data && data.alternatives) || {};
      var a = alts.min_time;
      var b = alts.min_transfer;
      if (a && b) {
        var dt = Number(b.total_time_minutes_rounded || 0) - Number(a.total_time_minutes_rounded || 0);
        if (dt <= 8) {
          return "对比结果：两方案耗时接近，优先推荐换乘更少的方案。";
        }
        return "对比结果：最短时间方案节省时间更明显，优先推荐更快到达路线。";
      }
      return "本次按所选策略输出推荐。";
    }

    function buildSceneFocusText(mode) {
      var m = mode || "commute";
      var p = MODE_PROFILE[m] || MODE_PROFILE.commute;
      return p.title + "：关注「" + p.concerns.join("、") + "」。" + p.tips;
    }

    function applyModeTheme(mode) {
      var m = mode || "commute";
      var b = document.body;
      if (b) {
        b.setAttribute("data-guide-mode", m);
      }
    }

    function renderSceneFocus(mode) {
      if (!sceneFocusPanel) {
        return;
      }
      var m = mode || "commute";
      var p = MODE_PROFILE[m] || MODE_PROFILE.commute;
      sceneFocusPanel.textContent = p.title + "：最在意 " + p.concerns.join("、") + "。";
      sceneFocusPanel.classList.add("scene-focus-panel");
      if (metricLinePlan && metricTransferPlan) {
        if (m === "rush") {
          metricLinePlan.previousElementSibling && (metricLinePlan.previousElementSibling.textContent = "线路建议（速度优先）");
          metricTransferPlan.previousElementSibling &&
            (metricTransferPlan.previousElementSibling.textContent = "换乘建议（少等待）");
        } else if (m === "senior") {
          metricLinePlan.previousElementSibling && (metricLinePlan.previousElementSibling.textContent = "线路建议（少折返）");
          metricTransferPlan.previousElementSibling &&
            (metricTransferPlan.previousElementSibling.textContent = "换乘建议（少步行）");
        } else if (m === "tour") {
          metricLinePlan.previousElementSibling && (metricLinePlan.previousElementSibling.textContent = "线路建议（易识别）");
          metricTransferPlan.previousElementSibling &&
            (metricTransferPlan.previousElementSibling.textContent = "换乘建议（导引友好）");
        } else {
          metricLinePlan.previousElementSibling && (metricLinePlan.previousElementSibling.textContent = "线路建议（稳定通勤）");
          metricTransferPlan.previousElementSibling &&
            (metricTransferPlan.previousElementSibling.textContent = "换乘建议（可预测）");
        }
      }
    }

    function keyStationsForA11y(steps) {
      if (!steps || !steps.length) {
        return [];
      }
      var transfer = {};
      for (var i = 0; i < steps.length - 1; i++) {
        if (steps[i].line !== steps[i + 1].line) {
          transfer[steps[i + 1].station] = 1;
        }
      }
      var order = [];
      var se = {};
      for (var j = 0; j < steps.length; j++) {
        var st = steps[j].station;
        if (!se[st]) {
          se[st] = 1;
          order.push(st);
        }
      }
      var start = order[0];
      var end = order[order.length - 1];
      return order.map(function (name) {
        var role;
        if (name === start && name === end) {
          role = "起终点";
        } else if (name === start) {
          role = "起点";
        } else if (name === end) {
          role = "终点";
        } else if (transfer[name]) {
          role = "换乘";
        } else {
          role = "途经";
        }
        return { name: name, role: role };
      });
    }

    function rolePillClass(role) {
      if (role === "起点" || role === "起终点") {
        return "role-pill role-pill--start";
      }
      if (role === "终点") {
        return "role-pill role-pill--end";
      }
      if (role === "换乘") {
        return "role-pill role-pill--xfer";
      }
      return "role-pill role-pill--via";
    }

    function renderA11yCards(rolesList, batch) {
      resultA11yList.innerHTML = "";
      a11yResultStatus.hidden = true;
      if (!batch || !batch.stations) {
        a11yResultStatus.hidden = false;
        a11yResultStatus.textContent = "未获取到无障碍数据。";
        return;
      }
      var stMap = batch.stations;
      var focusKeys = MODE_FOCUS[currentGuideMode] || [];
      var focusSet = {};
      for (var fi = 0; fi < focusKeys.length; fi++) {
        focusSet[focusKeys[fi]] = true;
      }
      var preferredOrder = focusKeys.concat(["blind_path", "remark"]);
      for (var k = 0; k < rolesList.length; k++) {
        var _ = rolesList[k];
        var name = _.name;
        var role = _.role;
        var data = stMap[name];
        var card = document.createElement("article");
        card.className = "a11y-card";
        var head = document.createElement("div");
        head.className = "a11y-card__head";
        var strong = document.createElement("strong");
        strong.textContent = name;
        var span = document.createElement("span");
        span.className = rolePillClass(role);
        span.textContent = role;
        head.appendChild(strong);
        head.appendChild(span);
        card.appendChild(head);
        var dl = document.createElement("div");
        dl.className = "a11y-dl";
        if (data && typeof data === "object") {
          var keys = Object.keys(data);
          keys.sort(function (a, b) {
            var ia = preferredOrder.indexOf(a);
            var ib = preferredOrder.indexOf(b);
            if (ia === -1) ia = 999;
            if (ib === -1) ib = 999;
            return ia - ib;
          });
          for (var m = 0; m < keys.length; m++) {
            var cell = data[keys[m]];
            if (!cell || typeof cell !== "object") {
              continue;
            }
            var row = document.createElement("div");
            var dt = document.createElement("dt");
            var dd = document.createElement("dd");
            var label = cell.label || FIELD_LABELS[keys[m]] || keys[m];
            if (focusSet[keys[m]]) {
              label = "重点 · " + label;
            }
            dt.textContent = label;
            var val = cell.value != null ? String(cell.value) : "暂未收录";
            dd.textContent = val;
            if (val === "暂未收录") {
              dd.style.color = "var(--muted)";
            }
            if (focusSet[keys[m]]) {
              row.classList.add("a11y-row-focus");
              dt.classList.add("a11y-focus-key");
              dd.classList.add("a11y-focus-value");
            }
            row.appendChild(dt);
            row.appendChild(dd);
            dl.appendChild(row);
          }
        } else {
          var p = document.createElement("p");
          p.className = "section-lead";
          p.textContent = "本站点无结构化数据，请洽客服或现场引导。";
          card.appendChild(p);
        }
        card.appendChild(dl);
        resultA11yList.appendChild(card);
      }
    }

    function fetchA11yBatch(stationNames) {
      return jsonFetch("/api/accessibility/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stations: stationNames }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          if (j && j.ok === false) {
            return { err: (j && j.error) || "无障碍接口错误" };
          }
          return { data: j };
        })
        .catch(function (e) {
          return { err: (e && e.message) || String(e) };
        });
    }

    function renderError(msg) {
      resultSection.classList.add("hidden");
      resultSection.classList.remove("result-section--compare-alts-top");
      resultSection.setAttribute("aria-hidden", "true");
      emptyHint.classList.remove("hidden");
      emptyHint.textContent = msg;
      if (routeOpStatusPanel) {
        routeOpStatusPanel.classList.add("hidden");
      }
      setStatus("error", msg);
    }

    function renderSuccess(data) {
      var p = data.plan;
      lastPlanPayload = data;
      if (!p) {
        setStatus("error", "返回数据异常：缺少 plan 字段。");
        return;
      }
      resultSection.classList.remove("hidden");
      resultSection.setAttribute("aria-hidden", "false");
      if (data.strategy === "compare") {
        resultSection.classList.add("result-section--compare-alts-top");
      } else {
        resultSection.classList.remove("result-section--compare-alts-top");
      }
      emptyHint.classList.add("hidden");
      var steps = p.steps || [];
      var summary = buildLineAndTransferSummary(steps);
      var svc = data && data.service_time_check;
      var qh = (svc && svc.query_hhmm) || "";
      if (metricTime) {
        metricTime.textContent = formatMinutes(p.total_time_minutes_rounded) + " 分";
      }
      if (metricArrival) {
        metricArrival.textContent = computeArrivalHhmm(qh, p.total_time_minutes_rounded);
      }
      if (metricFare) {
        metricFare.textContent =
          p.estimated_fare_yuan != null ? p.estimated_fare_yuan + " 元" : "—";
      }
      if (metricXfer) {
        metricXfer.textContent = p.transfer_count != null ? String(p.transfer_count) + " 次" : "—";
      }
      if (metricLinePlan) {
        metricLinePlan.textContent = summary.lines;
      }
      if (metricTransferPlan) {
        metricTransferPlan.textContent = summary.transfers;
      }
      if (svc && svc.ok) {
        if (metricServiceCheck) {
          metricServiceCheck.textContent = "按模型，当前查询时刻可乘车（以现场时刻表为准）";
        }
      } else if (svc) {
        if (metricServiceCheck) {
          metricServiceCheck.textContent =
            "有乘车路线，但按当前时刻与首末班模型可能不可行（见下方说明）。";
        }
      } else {
        if (metricServiceCheck) {
          metricServiceCheck.textContent = "未提供首末班校验。";
        }
      }
      renderTransitRoute(steps);
      if (recommendReason) {
        recommendReason.textContent =
          buildSceneFocusText(currentGuideMode) + " " + buildRecommendationFallback(data);
      }
      renderSceneFocus(currentGuideMode);
      renderRouteOpPanel(data, steps);
      guideText.textContent = data.guide_text || "（未返回文字指南）";
      renderAlternatives(data.alternatives || null);
      if (data.elapsed_seconds != null) {
        setStatus("hint", "本次服务端耗时约 " + data.elapsed_seconds + " 秒。");
      } else {
        setStatus("", "");
      }
      var roles = keyStationsForA11y(steps);
      lastQueryContext = {
        from_station: data && data.resolved ? data.resolved.from : (elFrom.value || "").trim(),
        to_station: data && data.resolved ? data.resolved.to : (elTo.value || "").trim(),
        strategy: data && data.strategy ? data.strategy : "min_time",
      };
      a11yResultStatus.hidden = false;
      a11yResultStatus.className = "status loading";
      a11yResultStatus.textContent = "正在拉取本行程各站无障碍信息…";
      resultA11yList.innerHTML = "";
      var names = roles.map(function (r) {
        return r.name;
      });
      fetchA11yBatch(names).then(function (out) {
        a11yResultStatus.hidden = true;
        if (out.err) {
          a11yResultStatus.hidden = false;
          a11yResultStatus.className = "status error";
          a11yResultStatus.textContent = out.err;
          return;
        }
        renderA11yCards(roles, out.data);
      });
    }

    function copyGuide() {
      var txt = guideText ? (guideText.textContent || "").trim() : "";
      if (!txt) {
        setStatus("error", "当前没有可复制的路线文本。");
        return;
      }
      navigator.clipboard.writeText(txt)
        .then(function () {
          setStatus("hint", "路线文本已复制到剪贴板。");
        })
        .catch(function () {
          setStatus("error", "复制失败，请手动选中文本复制。");
        });
    }

    function exportGuide() {
      if (!lastPlanPayload) {
        setStatus("error", "请先查询一次路线再导出。");
        return;
      }
      var txt = String(lastPlanPayload.guide_text || "");
      var meta = "起点：" + (lastPlanPayload.resolved && lastPlanPayload.resolved.from || "") +
        "\n终点：" + (lastPlanPayload.resolved && lastPlanPayload.resolved.to || "") +
        "\n策略：" + (lastPlanPayload.strategy || "") + "\n\n";
      var blob = new Blob([meta + txt], { type: "text/plain;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "subway_guide_" + Date.now() + ".txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      setStatus("hint", "已导出本次指南文本。");
    }

    function setFbStatus(type, text) {
      fbStatus.className = "status " + (type || "");
      fbStatus.textContent = text || "";
    }

    function submitFeedback() {
      var issueType = fbIssueType && fbIssueType.value ? fbIssueType.value : "other";
      var severity = fbSeverity && fbSeverity.value ? fbSeverity.value : "medium";
      var content = (fbContent && fbContent.value ? fbContent.value : "").trim();
      var contact = (fbContact && fbContact.value ? fbContact.value : "").trim();
      var reproducible = !!(fbRepro && fbRepro.checked);
      if (content.length < 6) {
        setFbStatus("error", "反馈内容至少 6 个字符。");
        return;
      }
      var ctx = lastQueryContext || {
        from_station: (elFrom.value || "").trim(),
        to_station: (elTo.value || "").trim(),
        strategy: "unknown",
      };
      fbSubmitBtn.disabled = true;
      setFbStatus("loading", "正在提交反馈…");
      jsonFetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issue_type: issueType,
          severity: severity,
          content: content,
          reproducible: reproducible,
          contact: contact,
          from_station: ctx.from_station || "",
          to_station: ctx.to_station || "",
          strategy: ctx.strategy || "",
        }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || d.ok === false) {
            setFbStatus("error", (d && d.error) || "提交失败，请稍后重试。");
            return;
          }
          setFbStatus("hint", "反馈提交成功，感谢你的建议！");
          if (fbContent) fbContent.value = "";
          if (fbRepro) fbRepro.checked = false;
        })
        .catch(function (e) {
          setFbStatus("error", "提交失败：" + ((e && e.message) || "网络异常"));
        })
        .then(function () {
          fbSubmitBtn.disabled = false;
        });
    }

    function renderAlternatives(alts) {
      alternativesGrid.innerHTML = "";
      if (!alts) {
        alternativesGrid.textContent = "无备选方案数据。";
        return;
      }
      var svc = (lastPlanPayload && lastPlanPayload.alternatives_service_check) || {};
      var keys = ["min_time", "min_transfer"];
      var labels = {
        min_time: "方案A：最短时间",
        min_transfer: "方案B：最少换乘",
      };
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var p = alts[k];
        if (!p) continue;
        var card = document.createElement("article");
        card.className = "alt-card";
        var h3 = document.createElement("h3");
        h3.textContent = labels[k];
        var ms = document.createElement("div");
        ms.className = "alt-metrics";
        ms.textContent =
          "时间 " +
          formatMinutes(p.total_time_minutes_rounded) +
          " 分 / 换乘 " +
          (p.transfer_count != null ? p.transfer_count : "—") +
          " 次 / 票价 " +
          (p.estimated_fare_yuan != null ? p.estimated_fare_yuan + " 元" : "—");
        var svcText = document.createElement("div");
        svcText.className = "alt-metrics";
        var s = svc[k] || {};
        svcText.textContent = "时段：" + (s.ok ? "可行" : "不可行") + (s.message ? ("（" + s.message + "）") : "");
        card.appendChild(h3);
        card.appendChild(ms);
        card.appendChild(svcText);
        alternativesGrid.appendChild(card);
      }
    }

    function query() {
      var from = (elFrom.value || "").trim();
      var to = (elTo.value || "").trim();
      var selected = document.querySelector('input[name="strategy"]:checked');
      var strat = selected ? selected.value : "min_time";
      var guideMode = elGuideMode && elGuideMode.value ? elGuideMode.value : "commute";
      currentGuideMode = guideMode;
      applyModeTheme(currentGuideMode);
      if (!from || !to) {
        setStatus("error", "请填写起点与终点站名。");
        return;
      }
      showLoading(true);
      setStatus("loading", "请求中…");
      resultSection.classList.add("hidden");
      resultSection.setAttribute("aria-hidden", "true");
      emptyHint.classList.add("hidden");
      ensureApiBase().then(function () {
        var body = { from: from, to: to, strategy: strat, guide_mode: guideMode };
        if (elQueryTime && elQueryTime.value) {
          body.query_time = elQueryTime.value;
        }
        return jsonFetch("/api/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      })
        .then(function (r) {
          return r.json().then(function (d) {
            return { r: r, d: d };
          });
        })
        .then(function (ref) {
          var r = ref.r;
          var data = ref.d;
          if (r.status === 401) {
            return;
          }
          if (!r.ok) {
            renderError((data && data.error) || "请求失败（HTTP " + r.status + "）");
            return;
          }
          if (data.ok === false) {
            renderError(data.error || "无可用结果");
            return;
          }
          if (!data.ok) {
            renderError(data.error || "服务返回异常。");
            return;
          }
          renderSuccess(data);
          if (data.recommendation_reason) {
            setStatus("hint", data.recommendation_reason);
          }
        })
        .catch(function (e) {
          if (e && e.message === "需要登录") {
            return;
          }
          renderError("网络或服务器错误。请运行 py -3 api_server.py 并同域访问。 " + (e && e.message ? e.message : ""));
        })
        .then(function () {
          showLoading(false);
        });
    }

    function renderRules(d) {
      var acc = $("rulesAccordion");
      if (!d || !d.items) {
        rulesLoadStatus.textContent = "数据为空或格式错误。";
        rulesLoadStatus.classList.add("is-error");
        return;
      }
      if (d.description) {
        $("rulesIntro").textContent =
          d.description + " 维护时编辑 data/reference/passenger_rules.json 。";
      }
      acc.innerHTML = "";
      for (var i = 0; i < d.items.length; i++) {
        (function (it) {
          var det = document.createElement("details");
          var sum = document.createElement("summary");
          sum.textContent = it.title;
          if (it.summary) {
            var s = document.createElement("span");
            s.className = "acc-sum";
            s.textContent = it.summary;
            sum.appendChild(document.createElement("br"));
            sum.appendChild(s);
          }
          var body = document.createElement("p");
          body.className = "acc-body";
          body.textContent = it.content || "";
          det.appendChild(sum);
          det.appendChild(body);
          acc.appendChild(det);
        })(d.items[i]);
      }
      rulesLoadStatus.textContent = "已加载 " + d.items.length + " 条规则。";
    }

    function pitemClass(color) {
      var m = {
        hazard: "pitem-card--hazard",
        weapon: "pitem-card--weapon",
        chemical: "pitem-card--chemical",
        bio: "pitem-card--bio",
      };
      return "pitem-card " + (m[color] || "pitem-card--hazard");
    }

    function renderProhibited(d) {
      var grid = $("prohibitedGrid");
      if (!d || !d.categories) {
        prohibitedLoadStatus.textContent = "数据为空或格式错误。";
        prohibitedLoadStatus.classList.add("is-error");
        return;
      }
      if (d.description) {
        var first = d.title ? d.title + "。" : "";
        $("prohibitedIntro").textContent =
          first + d.description + " 数据文件：data/reference/prohibited_items.json 。";
      }
      grid.innerHTML = "";
      for (var c = 0; c < d.categories.length; c++) {
        (function (cat) {
          var el = document.createElement("div");
          el.className = pitemClass(cat.color);
          var head = document.createElement("div");
          head.className = "pitem-head";
          var ico = document.createElement("span");
          ico.className = "pitem-ico";
          ico.textContent = ICON_MAP[cat.icon] || "⛔";
          var tit = document.createElement("div");
          tit.className = "pitem-titles";
          var h3 = document.createElement("h3");
          h3.textContent = cat.label || cat.short_label;
          var short = document.createElement("span");
          short.className = "pitem-short";
          short.textContent = cat.short_label || cat.id;
          tit.appendChild(h3);
          tit.appendChild(document.createTextNode(" "));
          tit.appendChild(short);
          head.appendChild(ico);
          head.appendChild(tit);
          el.appendChild(head);
          if (cat.examples && cat.examples.length) {
            var ex = document.createElement("p");
            ex.className = "pitem-ex";
            ex.textContent = "示例：" + cat.examples.join("；");
            el.appendChild(ex);
          }
          var ul = document.createElement("ul");
          for (var t = 0; t < (cat.items || []).length; t++) {
            var li = document.createElement("li");
            li.textContent = cat.items[t];
            ul.appendChild(li);
          }
          el.appendChild(ul);
          if (cat.note) {
            var foot = document.createElement("div");
            foot.className = "pitem-foot";
            foot.textContent = cat.note;
            el.appendChild(foot);
          }
          grid.appendChild(el);
        })(d.categories[c]);
      }
      if (d.footer) {
        var f = document.createElement("p");
        f.className = "prohibited-page-foot";
        f.textContent = d.footer;
        grid.appendChild(f);
      }
      prohibitedLoadStatus.textContent = "已加载 " + d.categories.length + " 个类别。";
    }

    function loadReference() {
      function fetchJsonSafe(path) {
        return ensureApiBase()
          .then(function () { return jsonFetch(path); })
          .then(function (r) {
            var ct = (r.headers.get("content-type") || "").toLowerCase();
            if (ct.indexOf("application/json") < 0) return { ok: false, error: "非JSON响应" };
            return r.json();
          })
          .catch(function (e) {
            return { ok: false, error: (e && e.message) || "网络异常" };
          });
      }

      fetchJsonSafe("/api/reference/passenger-rules").then(function (r1) {
        if (r1 && r1.ok && r1.data) {
          renderRules(r1.data);
        } else {
          rulesLoadStatus.textContent = "需登录后加载。若已登录，请检查后端与网络。";
          rulesLoadStatus.classList.add("is-error");
        }
      });
      fetchJsonSafe("/api/reference/prohibited-items").then(function (r2) {
        if (r2 && r2.ok && r2.data) {
          renderProhibited(r2.data);
        } else {
          prohibitedLoadStatus.textContent = "禁带物品加载失败。";
          prohibitedLoadStatus.classList.add("is-error");
        }
      });
      fetchJsonSafe("/api/reference/station-accessibility-meta").then(function (r3) {
        if (r3 && r3.ok && r3.data && r3.data.meta) {
          var t = (r3.data.meta.page_intro || "").trim();
          a11yMeta.textContent = t || "（无总体说明）";
          a11yMeta.removeAttribute("data-placeholder");
        } else {
          a11yMeta.textContent = "元数据未加载。";
          a11yMeta.classList.add("is-error");
        }
      });
    }

    btn.addEventListener("click", query);
    if (elGuideMode) {
      elGuideMode.addEventListener("change", function () {
        currentGuideMode = elGuideMode.value || "commute";
        applyModeTheme(currentGuideMode);
        renderSceneFocus(currentGuideMode);
      });
    }
    if (copyGuideBtn) copyGuideBtn.addEventListener("click", copyGuide);
    if (exportGuideBtn) exportGuideBtn.addEventListener("click", exportGuide);
    fbSubmitBtn.addEventListener("click", submitFeedback);
    elFrom.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        query();
      }
    });
    elTo.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        query();
      }
    });
    applyModeTheme(currentGuideMode);
    renderSceneFocus(currentGuideMode);
    loadReference();
  }

  function start() {
    if (!window.__appBoot) {
      return;
    }
    window.__appBoot
      .then(function (b) {
        main(b);
      })
      .catch(function () {
        location.replace("/login.html?next=" + encodeURIComponent("/app.html"));
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
