(function () {
  function q(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toNum(v) {
    if (v == null || v === "") return "0";
    return String(v);
  }

  function statusLabel(s) {
    if (s === "pending") return "待处理";
    if (s === "in_progress") return "处理中";
    if (s === "resolved") return "已解决";
    return s || "";
  }
  function issueLabel(t) {
    var m = {
      route_bad: "路线不合理",
      station_outdated: "站点信息过时",
      a11y_error: "无障碍信息错误",
      other: "其他",
    };
    return m[t] || t || "";
  }
  function severityLabel(s) {
    var m = { high: "高", medium: "中", low: "低" };
    return m[s] || s || "";
  }

  function ensureAdmin() {
    return window
      .apiFetch("/api/auth/me")
      .then(function (r) {
        if (r.status === 401) {
          location.replace("/login.html?next=" + encodeURIComponent("/admin.html"));
          return null;
        }
        return r.json();
      })
      .then(function (d) {
        if (!d || !d.user) return null;
        if (!d.user.is_admin) {
          location.replace("/app.html");
          return null;
        }
        q("adminGreet").textContent = "管理员：" + d.user.username;
        return d.user;
      });
  }

  function renderTable(containerId, headers, rows) {
    var wrap = q(containerId);
    wrap.innerHTML = "";
    if (!rows || !rows.length) {
      wrap.innerHTML = '<p class="section-lead">暂无数据。</p>';
      return;
    }
    var t = document.createElement("table");
    t.className = "data-table";
    var head = "<thead><tr>" + headers.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("") + "</tr></thead>";
    var body = "<tbody>" + rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody>";
    t.innerHTML = head + body;
    wrap.appendChild(t);
  }

  function loadSummary() {
    return window
      .apiFetch("/api/admin/summary")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.data) throw new Error("summary");
        q("mUsers").textContent = toNum(d.data.total_users);
        q("mQueries").textContent = toNum(d.data.total_queries);
        q("mActive").textContent = toNum(d.data.active_users_7d);
        q("mFeedback").textContent = toNum(d.data.total_feedback);
        q("mFeedbackPending").textContent = toNum(d.data.pending_feedback);
        q("mFeedbackOverdue").textContent = toNum((d.data.overdue_unprocessed != null ? d.data.overdue_unprocessed : 0));
        q("summaryStatus").textContent = "";
      })
      .catch(function () {
        q("summaryStatus").className = "ref-status is-error";
        q("summaryStatus").textContent = "系统概览加载失败。";
      });
  }

  function loadUsers() {
    return window
      .apiFetch("/api/admin/users?limit=200")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        q("usersStatus").textContent = "";
        if (!d || !d.ok || !d.items) throw new Error("users");
        var wrap = q("usersTable");
        wrap.innerHTML = "";
        if (!d.items.length) {
          wrap.innerHTML = '<p class="section-lead">暂无用户。</p>';
          return;
        }
        var t = document.createElement("table");
        t.className = "data-table";
        t.innerHTML =
          "<thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>注册时间</th><th>查询次数</th><th>最近查询</th><th>操作</th></tr></thead><tbody></tbody>";
        var tb = t.querySelector("tbody");
        d.items.forEach(function (u) {
          var tr = document.createElement("tr");
          tr.innerHTML =
            "<td>" + esc(u.id) + "</td>" +
            "<td>" + esc(u.username) + "</td>" +
            "<td>" + esc((u.role || "passenger")) + "</td>" +
            "<td>" + esc(u.created_at || "") + "</td>" +
            "<td>" + esc(u.query_count || 0) + "</td>" +
            "<td>" + esc(u.last_query_at || "—") + "</td>" +
            "<td>" +
              "<select data-k='role'>" +
                "<option value='passenger'" + ((u.role || "passenger") === "passenger" ? " selected" : "") + ">passenger</option>" +
                "<option value='admin'" + ((u.role || "passenger") === "admin" ? " selected" : "") + ">admin</option>" +
              "</select> " +
              "<button type='button' class='link-btn' data-k='save-role'>保存</button>" +
            "</td>";
          tb.appendChild(tr);
          var btn = tr.querySelector('button[data-k="save-role"]');
          btn.addEventListener("click", function () {
            var sel = tr.querySelector('select[data-k="role"]');
            btn.disabled = true;
            window.apiFetch("/api/admin/users/" + encodeURIComponent(String(u.id)) + "/role", {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ role: sel.value }),
            })
              .then(function (r) { return r.json().then(function (d) { return { r: r, d: d }; }); })
              .then(function (res) {
                if (!res.r.ok || !res.d || res.d.ok === false) {
                  throw new Error((res.d && res.d.error) || "角色更新失败");
                }
                q("usersStatus").textContent = "用户角色已更新。";
                loadUsers();
              })
              .catch(function (e) {
                q("usersStatus").className = "ref-status is-error";
                q("usersStatus").textContent = "角色更新失败：" + ((e && e.message) || "");
              })
              .then(function () {
                btn.disabled = false;
              });
          });
        });
        wrap.appendChild(t);
      })
      .catch(function () {
        q("usersStatus").className = "ref-status is-error";
        q("usersStatus").textContent = "用户列表加载失败。";
      });
  }

  function loadHistory() {
    return window
      .apiFetch("/api/admin/history?limit=150")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        q("historyStatus").textContent = "";
        if (!d || !d.ok || !d.items) throw new Error("history");
        var rows = d.items.map(function (it) {
          return [
            it.created_at || "",
            it.username || "",
            it.from_station || "",
            it.to_station || "",
            it.strategy || "",
            it.total_time_minutes == null ? "—" : it.total_time_minutes,
            it.transfer_count == null ? "—" : it.transfer_count,
            it.estimated_fare_yuan == null ? "—" : it.estimated_fare_yuan,
          ];
        });
        renderTable(
          "historyTable",
          ["时间", "用户", "起点", "终点", "策略", "时间(分)", "换乘", "票价(元)"],
          rows
        );
      })
      .catch(function () {
        q("historyStatus").className = "ref-status is-error";
        q("historyStatus").textContent = "查询记录加载失败。";
      });
  }

  function updateFeedback(id, status, note) {
    return window.apiFetch("/api/admin/feedback/" + encodeURIComponent(String(id)), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status, resolution_note: note || "" }),
    }).then(function (r) { return r.json(); });
  }

  function renderFeedbackTable(items) {
    var wrap = q("feedbackAdminTable");
    wrap.innerHTML = "";
    if (!items || !items.length) {
      wrap.innerHTML = '<p class="section-lead">暂无反馈数据。</p>';
      return;
    }
    var t = document.createElement("table");
    t.className = "data-table";
    t.innerHTML =
      "<thead><tr><th>ID</th><th>时间</th><th>用户</th><th>类型</th><th>严重程度</th><th>SLA</th><th>内容</th><th>行程</th><th>状态</th><th>处理备注</th><th>操作</th></tr></thead><tbody></tbody>";
    var tb = t.querySelector("tbody");
    items.forEach(function (it) {
      var tr = document.createElement("tr");
      var route = (it.from_station || "—") + " → " + (it.to_station || "—");
      var sla = Number(it.is_overdue || 0) === 1 ? ("超时(" + (it.pending_hours || 0) + "h)") : ("正常(" + (it.pending_hours || 0) + "h)");
      tr.innerHTML =
        "<td>" + esc(it.id) + "</td>" +
        "<td>" + esc(it.created_at || "") + "</td>" +
        "<td>" + esc(it.username || "") + "</td>" +
        "<td>" + esc(issueLabel(it.issue_type || "")) + "</td>" +
        "<td>" + esc(severityLabel(it.severity || "")) + "</td>" +
        "<td>" + esc(sla) + "</td>" +
        "<td>" + esc(it.content || "") + "</td>" +
        "<td>" + esc(route) + "</td>" +
        "<td>" + esc(statusLabel(it.status)) + "</td>" +
        "<td><input type='text' data-k='note' value='" + esc(it.resolution_note || "") + "' /></td>" +
        "<td>" +
        "<select data-k='status'>" +
        "<option value='pending'" + (it.status === "pending" ? " selected" : "") + ">待处理</option>" +
        "<option value='in_progress'" + (it.status === "in_progress" ? " selected" : "") + ">处理中</option>" +
        "<option value='resolved'" + (it.status === "resolved" ? " selected" : "") + ">已解决</option>" +
        "</select> " +
        "<button type='button' class='link-btn' data-k='save'>保存</button>" +
        "</td>";
      tb.appendChild(tr);
      var btn = tr.querySelector('button[data-k="save"]');
      btn.addEventListener("click", function () {
        var sel = tr.querySelector('select[data-k="status"]');
        var noteInput = tr.querySelector('input[data-k="note"]');
        btn.disabled = true;
        updateFeedback(it.id, sel.value, noteInput.value)
          .then(function (d) {
            if (!d || d.ok === false) throw new Error((d && d.error) || "更新失败");
            q("feedbackAdminStatus").textContent = "反馈 #" + it.id + " 已更新。";
          })
          .catch(function (e) {
            q("feedbackAdminStatus").className = "ref-status is-error";
            q("feedbackAdminStatus").textContent = "更新失败：" + ((e && e.message) || "");
          })
          .then(function () {
            btn.disabled = false;
          });
      });
    });
    wrap.appendChild(t);
  }

  function loadFeedback() {
    var status = q("fbFilterStatus").value || "all";
    var issueType = q("fbFilterIssueType").value || "all";
    var fromDate = q("fbFromDate").value || "";
    var toDate = q("fbToDate").value || "";
    q("feedbackAdminStatus").className = "ref-status";
    q("feedbackAdminStatus").textContent = "正在加载…";
    return window
      .apiFetch(
        "/api/admin/feedback?limit=200&status=" +
          encodeURIComponent(status) +
          "&issue_type=" + encodeURIComponent(issueType) +
          "&from_date=" + encodeURIComponent(fromDate) +
          "&to_date=" + encodeURIComponent(toDate)
      )
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.items) throw new Error("feedback");
        q("feedbackAdminStatus").textContent = "已加载 " + d.items.length + " 条反馈。";
        renderFeedbackTable(d.items);
      })
      .catch(function () {
        q("feedbackAdminStatus").className = "ref-status is-error";
        q("feedbackAdminStatus").textContent = "反馈列表加载失败。";
      });
  }

  function loadFeedbackStats() {
    return window
      .apiFetch("/api/admin/feedback/stats")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.data) throw new Error("feedback-stats");
        var bs = d.data.by_status || {};
        var bsev = d.data.by_severity || {};
        var bit = d.data.by_issue_type || {};
        q("fbStatPending").textContent = toNum(bs.pending || 0);
        q("fbStatInProgress").textContent = toNum(bs.in_progress || 0);
        q("fbStatResolved").textContent = toNum(bs.resolved || 0);
        q("fbStatHigh").textContent = toNum(bsev.high || 0);
        q("fbStatRoute").textContent = toNum(bit.route_bad || 0);
      })
      .catch(function () {
        q("feedbackAdminStatus").className = "ref-status is-error";
        q("feedbackAdminStatus").textContent = "反馈统计加载失败。";
      });
  }

  function renderTrend(items) {
    var wrap = q("fbTrendChart");
    var status = q("fbTrendStatus");
    wrap.innerHTML = "";
    if (!items || !items.length) {
      var empty = document.createElement("div");
      empty.className = "section-lead";
      empty.style.gridColumn = "1 / -1";
      empty.style.textAlign = "center";
      empty.style.margin = "0";
      empty.textContent = "暂无趋势数据。当前时间窗口内尚无反馈记录。";
      wrap.appendChild(empty);
      status.textContent = "暂无趋势数据。";
      return;
    }
    var total = 0;
    var maxCount = 1;
    for (var i = 0; i < items.length; i++) {
      total += Number(items[i].count || 0);
      if ((items[i].count || 0) > maxCount) maxCount = items[i].count || 0;
    }
    for (var j = 0; j < items.length; j++) {
      var it = items[j];
      var d = String(it.date || "");
      var c = Number(it.count || 0);
      var h = Math.max(4, Math.round((c / maxCount) * 90));
      var bar = document.createElement("div");
      bar.className = "trend-bar";
      var count = document.createElement("div");
      count.className = "trend-bar__count";
      count.textContent = String(c);
      var col = document.createElement("div");
      col.className = "trend-bar__col";
      col.style.height = h + "px";
      col.setAttribute("data-tip", d + "：" + c + " 条");
      col.title = d + "：" + c + " 条";
      var date = document.createElement("div");
      date.className = "trend-bar__date";
      date.textContent = d.slice(5);
      bar.appendChild(count);
      bar.appendChild(col);
      bar.appendChild(date);
      wrap.appendChild(bar);
    }
    if (total === 0) {
      status.textContent = "最近 " + items.length + " 天暂无新增反馈。";
    } else {
      status.textContent = "最近 " + items.length + " 天累计反馈 " + total + " 条。";
    }
  }

  function loadFeedbackTrend() {
    var checked = document.querySelector('input[name="trendDays"]:checked');
    var days = checked ? Number(checked.value || 7) : 7;
    return window
      .apiFetch("/api/admin/feedback/trend?days=" + encodeURIComponent(String(days)))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.items) throw new Error("feedback-trend");
        renderTrend(d.items);
      })
      .catch(function () {
        q("fbTrendStatus").className = "ref-status is-error";
        q("fbTrendStatus").textContent = "趋势数据加载失败。";
      });
  }

  q("btnLogout").addEventListener("click", function () {
    window.apiFetch("/api/auth/logout", { method: "POST" }).then(function () {
      location.assign("/");
    });
  });

  ensureAdmin().then(function (u) {
    if (!u) return;
    loadSummary();
    loadUsers();
    loadHistory();
    loadFeedbackStats();
    loadFeedbackTrend();
    loadFeedback();
  });
  q("fbReloadBtn").addEventListener("click", loadFeedback);
  q("fbReloadBtn").addEventListener("click", loadFeedbackStats);
  q("fbReloadBtn").addEventListener("click", loadFeedbackTrend);
  var trendRadios = document.querySelectorAll('input[name="trendDays"]');
  for (var i = 0; i < trendRadios.length; i++) {
    trendRadios[i].addEventListener("change", loadFeedbackTrend);
  }
  q("fbExportBtn").addEventListener("click", function () {
    var status = q("fbFilterStatus").value || "all";
    var issueType = q("fbFilterIssueType").value || "all";
    var fromDate = q("fbFromDate").value || "";
    var toDate = q("fbToDate").value || "";
    window.location.href =
      "/api/admin/feedback/export.csv?status=" + encodeURIComponent(status) +
      "&issue_type=" + encodeURIComponent(issueType) +
      "&from_date=" + encodeURIComponent(fromDate) +
      "&to_date=" + encodeURIComponent(toDate);
  });
})();
