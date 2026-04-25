(function () {
  function q(id) {
    return document.getElementById(id);
  }
  function nextParam() {
    var s = new URLSearchParams(window.location.search);
    return s.get("next") || "/app.html";
  }
  var form = q("formLogin");
  var st = q("loginStatus");
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    st.textContent = "登录中…";
    st.className = "ref-status";
    var body = {
      username: (q("username").value || "").trim(),
      password: q("password").value || "",
      remember: q("remember").checked,
    };
    window
      .apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (_ref) {
        var r = _ref.r;
        var d = _ref.d;
        if (r.status === 429) {
          st.className = "ref-status is-error";
          st.textContent = (d && d.error) || "尝试过于频繁。";
          return;
        }
        if (!r.ok) {
          st.className = "ref-status is-error";
          st.textContent = (d && d.error) || "登录失败。";
          return;
        }
        st.textContent = "登录成功，正在跳转…";
        var target = nextParam();
        var role = (d && d.user && d.user.role) ? String(d.user.role) : "passenger";
        if (target.indexOf("http") === 0) {
          target = (role === "admin") ? "/admin.html" : "/app.html";
        }
        if (target === "/app.html" && role === "admin" && window.location.search.indexOf("next=") < 0) {
          target = "/admin.html";
        }
        location.assign(target);
      })
      .catch(function (e) {
        st.className = "ref-status is-error";
        st.textContent = "网络错误：请确认已在本机运行 py -3 api_server.py";
      });
  });
})();
