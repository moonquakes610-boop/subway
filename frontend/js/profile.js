(function () {
  function q(id) {
    return document.getElementById(id);
  }
  var greet = q("profileGreet");
  var uinfo = q("userInfo");
  var hist = q("historyTable");
  var hst = q("historyStatus");
  var pstat = q("profileStatus");
  var fbst = q("feedbackStatus");
  var fbtb = q("feedbackTable");
  var pavatar = q("profileAvatar");

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
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

  window.apiFetch("/api/auth/me", { credentials: "include" })
    .then(function (r) {
      if (r.status === 401) {
        location.replace("/login.html?next=" + encodeURIComponent("/profile.html"));
        return null;
      }
      return r.json();
    })
    .then(function (d) {
      if (!d || !d.user) return;
      greet.textContent = "欢迎，" + d.user.username;
      var adminLink = q("navAdminLink");
      if (adminLink && !d.user.is_admin) {
        adminLink.style.display = "none";
      }
      uinfo.innerHTML = "";
      function row(label, val) {
        var div = document.createElement("div");
        var dt = document.createElement("dt");
        var dd = document.createElement("dd");
        dt.textContent = label;
        dd.textContent = val;
        div.appendChild(dt);
        div.appendChild(dd);
        uinfo.appendChild(div);
      }
      row("用户名", d.user.username);
      row("头像", d.user.avatar || "🙂");
      row("用户 ID", String(d.user.id));
      if (d.user.created_at) row("注册时间", d.user.created_at);
      if (pavatar) {
        pavatar.textContent = d.user.avatar || "🙂";
      }
    })
    .catch(function () {
      pstat.className = "ref-status is-error";
      pstat.textContent = "无法获取账户信息。";
    });

  window
    .apiFetch("/api/history?limit=15", { credentials: "include" })
    .then(function (r) {
      if (r.status === 401) {
        hst.textContent = "";
        return null;
      }
      return r.json();
    })
    .then(function (d) {
      hst.textContent = "";
      if (!d || !d.items) {
        hst.textContent = "无法加载历史。";
        return;
      }
      if (!d.items.length) {
        hist.innerHTML = '<p class="section-lead">暂无历史记录。登录后在「核心功能」中成功查询会在此列出。</p>';
        return;
      }
      var t = document.createElement("table");
      t.className = "data-table";
      t.innerHTML =
        "<thead><tr><th>时间</th><th>起点</th><th>终点</th><th>策略</th><th>时间(分)</th><th>换乘</th><th>票价(元)</th></tr></thead><tbody></tbody>";
      var tb = t.querySelector("tbody");
      d.items.forEach(function (it) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(it.created_at) +
          "</td><td>" +
          esc(it.from_station) +
          "</td><td>" +
          esc(it.to_station) +
          "</td><td>" +
          esc(it.strategy) +
          "</td><td>" +
          esc(it.total_time_minutes) +
          "</td><td>" +
          esc(it.transfer_count) +
          "</td><td>" +
          esc(it.estimated_fare_yuan) +
          "</td>";
        tb.appendChild(tr);
      });
      hist.appendChild(t);
    });

  window
    .apiFetch("/api/feedback/my?limit=20", { credentials: "include" })
    .then(function (r) {
      if (r.status === 401) {
        fbst.textContent = "";
        return null;
      }
      return r.json();
    })
    .then(function (d) {
      fbst.textContent = "";
      if (!d || !d.items) {
        fbst.textContent = "无法加载反馈记录。";
        return;
      }
      if (!d.items.length) {
        fbtb.innerHTML = '<p class="section-lead">你还没有提交反馈。</p>';
        return;
      }
      var t = document.createElement("table");
      t.className = "data-table";
      t.innerHTML =
        "<thead><tr><th>时间</th><th>问题类型</th><th>严重程度</th><th>问题描述</th><th>状态</th><th>处理备注</th></tr></thead><tbody></tbody>";
      var tb = t.querySelector("tbody");
      d.items.forEach(function (it) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(it.created_at || "") +
          "</td><td>" +
          esc(issueLabel(it.issue_type || "")) +
          "</td><td>" +
          esc(severityLabel(it.severity || "")) +
          "</td><td>" +
          esc(it.content || "") +
          "</td><td>" +
          esc(it.status || "") +
          "</td><td>" +
          esc(it.resolution_note || "—") +
          "</td>";
        tb.appendChild(tr);
      });
      fbtb.appendChild(t);
    });

  q("btnLogout").addEventListener("click", function () {
    window
      .apiFetch("/api/auth/logout", { method: "POST" })
      .then(function () {
        location.assign("/");
      });
  });
})();
