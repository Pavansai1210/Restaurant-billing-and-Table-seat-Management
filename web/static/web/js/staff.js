// Shared by every staff page: the login pass, the quiet refresh, and the role check.
const STAFF = (function () {
  // The page of each role. A role that is not listed here has no page yet.
  const HOME = { admin: '/panel/', chef: '/kitchen/', waiter: '/waiter/', cashier: '/cashier/', gate: '/gate/' };

  function read() {
    try {
      return JSON.parse(sessionStorage.getItem('rms_staff') || 'null');
    } catch (error) {
      return null;
    }
  }

  function save(data) {
    sessionStorage.setItem('rms_staff', JSON.stringify(data));
  }

  function forget() {
    sessionStorage.removeItem('rms_staff');
  }

  function logout() {
    forget();
    window.location.href = '/staff/login/';
  }

  function homeFor(role) {
    return HOME[role] || null;
  }

  async function raw(method, path, body, access) {
    const headers = { 'Content-Type': 'application/json' };
    if (access) {
      headers['Authorization'] = 'Bearer ' + access;
    }
    const options = { method: method, headers: headers };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    const reply = await fetch('/api' + path, options);
    let data = null;
    try {
      data = await reply.json();
    } catch (error) {
      data = null;
    }
    return { status: reply.status, data: data };
  }

  async function login(username, password) {
    const reply = await raw('POST', '/auth/login/', { username: username, password: password });
    if (reply.status === 200) {
      save({
        access: reply.data.access,
        refresh: reply.data.refresh,
        role: reply.data.role,
        username: reply.data.username
      });
    }
    return reply;
  }

  // Call an API with the pass. If it has expired, ask for a new one once, and try again.
  async function call(method, path, body) {
    const me = read();
    if (!me) {
      logout();
      return { status: 401, data: null };
    }
    let reply = await raw(method, path, body, me.access);
    if (reply.status === 401) {
      const again = await raw('POST', '/auth/refresh/', { refresh: me.refresh });
      if (again.status !== 200) {
        logout();
        return { status: 401, data: null };
      }
      me.access = again.data.access;
      save(me);
      reply = await raw(method, path, body, me.access);
      if (reply.status === 401) {
        logout();
      }
    }
    return reply;
  }

  // Use at the top of a staff page. require('chef', 'admin') lets both roles stay.
  // Anyone else is sent to his own page, or back to the login if his role has none.
  function require() {
    const roles = Array.prototype.slice.call(arguments);
    const me = read();
    if (!me) {
      window.location.href = '/staff/login/';
      return null;
    }
    if (roles.indexOf(me.role) === -1) {
      const home = homeFor(me.role);
      if (home) {
        window.location.href = home;
      } else {
        logout();
      }
      return null;
    }
    return me;
  }
  // Send a file with the pass. The browser sets the content type for a file by itself.
  async function upload(path, formData) {
    const me = read();
    if (!me) {
      logout();
      return { status: 401, data: null };
    }
    async function send(access) {
      const reply = await fetch('/api' + path, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + access },
        body: formData
      });
      let data = null;
      try {
        data = await reply.json();
      } catch (error) {
        data = null;
      }
      return { status: reply.status, data: data };
    }
    let reply = await send(me.access);
    if (reply.status === 401) {
      const again = await raw('POST', '/auth/refresh/', { refresh: me.refresh });
      if (again.status !== 200) {
        logout();
        return { status: 401, data: null };
      }
      me.access = again.data.access;
      save(me);
      reply = await send(me.access);
    }
    return reply;
  }
    return {
    read: read, login: login, logout: logout, forget: forget,
    call: call, upload: upload, require: require, homeFor: homeFor
  };
})();