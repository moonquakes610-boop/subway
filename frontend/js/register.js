(function () {
  function q(id) {
    return document.getElementById(id);
  }
  var form = q("formReg");
  var st = q("regStatus");
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    st.textContent = "提交中…";
    st.className = "ref-status";
    var p1 = q("password").value || "";
    var p2 = q("password2").value || "";
    if (p1.length < 8) {
      st.className = "ref-status is-error";
      st.textContent = "密码至少 8 位。";
      return;
    }
    if (p1 !== p2) {
      st.className = "ref-status is-error";
      st.textContent = "两次输入的密码不一致。";
      return;
    }
    var body = {
      username: (q("username").value || "").trim(),
      password: p1,
      password_confirm: p2,
      avatar: (q("avatar").value || "🙂"),
      role: (q("role").value || "passenger"),
    };
    window
      .apiFetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (_ref2) {
        var r = _ref2.r;
        var d = _ref2.d;
        if (!r.ok) {
          st.className = "ref-status is-error";
          st.textContent = (d && d.error) || "注册失败。";
          return;
        }
        st.textContent = "注册成功，请前往登录。";
        setTimeout(function () {
          var next = (body.role === "admin") ? "/admin.html" : "/app.html";
          location.assign("/login.html?next=" + encodeURIComponent(next));
        }, 500);
      })
      .catch(function () {
        st.className = "ref-status is-error";
        st.textContent = "网络错误，请检查后端。";
      });
  });
})();
