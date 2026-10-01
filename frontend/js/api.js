/* Thin fetch wrapper: adds the token, turns API errors into readable messages. */
(function () {
  const KEY = "freehold.token";
  const API = {
    token: null,
    load() { try { this.token = localStorage.getItem(KEY); } catch (e) { this.token = null; } return this.token; },
    save(t) { this.token = t; try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch (e) {} },
    onUnauthorized: null,
    async req(method, path, body, isForm) {
      const headers = {};
      if (this.token) headers.Authorization = "Bearer " + this.token;
      let payload;
      if (isForm) payload = body;
      else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
      let res;
      try { res = await fetch(path, { method, headers, body: payload }); }
      catch (e) { throw new Error("Cannot reach the server. Check your connection and try again."); }
      if (res.status === 401 && this.onUnauthorized && !path.startsWith("/api/auth/")) this.onUnauthorized();
      const text = await res.text();
      let data = null;
      if (text) { try { data = JSON.parse(text); } catch (e) { data = text; } }
      if (!res.ok) {
        let msg = "Something went wrong (" + res.status + ").";
        if (data && typeof data.detail === "string") msg = data.detail;
        else if (data && Array.isArray(data.detail)) msg = data.detail.map(d => d.msg).join("; ");
        const err = new Error(msg); err.status = res.status; throw err;
      }
      return data;
    },
    get(p) { return this.req("GET", p); },
    post(p, b) { return this.req("POST", p, b === undefined ? {} : b); },
    patch(p, b) { return this.req("PATCH", p, b); },
    del(p) { return this.req("DELETE", p); },
    upload(p, file) { const f = new FormData(); f.append("file", file); return this.req("POST", p, f, true); },
    fileUrl(p) { return p + (p.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(this.token || ""); },
  };
  window.API = API;
})();
