/* 同端口部署时留空，使用相对路径 /api/... 并自动携带 Cookie */
(function () {
  // 防呆：若用户误以 file:// 方式打开页面，自动跳转到本地 HTTP 服务入口。
  if (typeof location !== "undefined" && location.protocol === "file:") {
    location.replace("http://127.0.0.1:8765/");
    return;
  }
  if (typeof window.SUBWAY_API === "undefined") {
    window.SUBWAY_API = "";
  }
  window.getApiBase = function () {
    return String(window.SUBWAY_API || "").replace(/\/$/, "");
  };
  window.apiUrl = function (path) {
    var p = path && path.charAt(0) === "/" ? path : "/" + path;
    return window.getApiBase() + p;
  };
  var _csrfToken = "";
  var _csrfPromise = null;
  function _isUnsafeMethod(m) {
    var x = String(m || "GET").toUpperCase();
    return x === "POST" || x === "PUT" || x === "PATCH" || x === "DELETE";
  }
  function _pathOnly(path) {
    var p = String(path || "");
    var i = p.indexOf("?");
    return i >= 0 ? p.slice(0, i) : p;
  }
  function _ensureCsrfToken() {
    if (_csrfToken) return Promise.resolve(_csrfToken);
    if (_csrfPromise) return _csrfPromise;
    _csrfPromise = fetch(window.apiUrl("/api/auth/csrf"), { credentials: "include" })
      .then(function (r) {
        if (!r.ok) return {};
        var ct = (r.headers.get("content-type") || "").toLowerCase();
        if (ct.indexOf("application/json") < 0) return {};
        return r.json().catch(function () { return {}; });
      })
      .then(function (d) {
        _csrfToken = (d && d.csrf_token) || "";
        return _csrfToken;
      })
      .finally(function () {
        _csrfPromise = null;
      });
    return _csrfPromise;
  }
  window.apiFetch = function (path, init) {
    var o = init || {};
    o.credentials = o.credentials || "include";
    var method = String(o.method || "GET").toUpperCase();
    var p = _pathOnly(path);
    if (!_isUnsafeMethod(method) || p === "/api/auth/login" || p === "/api/auth/register" || p === "/api/auth/csrf") {
      return fetch(window.apiUrl(path), o);
    }
    return _ensureCsrfToken().then(function (tok) {
      var h = new Headers(o.headers || {});
      if (tok && !h.get("X-CSRF-Token")) {
        h.set("X-CSRF-Token", tok);
      }
      o.headers = h;
      return fetch(window.apiUrl(path), o);
    });
  };
})();
