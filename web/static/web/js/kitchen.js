(function () {
  const me = STAFF.require('chef', 'admin');
  if (!me) {
    return;
  }

  const notice = document.getElementById('notice');
  const alertsEl = document.getElementById('alerts');
  const waitersEl = document.getElementById('waiters');
  const ordersEl = document.getElementById('orders');

  document.getElementById('who').textContent = 'Logged in as ' + me.username + ' (' + me.role + ')';
  document.getElementById('logout').addEventListener('click', STAFF.logout);
  if (me.role === 'admin') {
    document.getElementById('to-panel').hidden = false;
  }

  const REFRESH_MS = 4000;
  const STATE_WORDS = { free: 'free', busy: 'busy', off_duty: 'off duty' };
  const GROUPS = [
    { status: 'placed', title: 'New orders' },
    { status: 'preparing', title: 'Being prepared' },
    { status: 'ready', title: 'Ready: give to a waiter' }
  ];

  let busy = false;       // true while a button action is running

  function minutesAgo(text) {
    return Math.max(0, Math.floor((Date.now() - new Date(text).getTime()) / 60000));
  }

  function problem(reply) {
    const d = reply.data;
    if (d && d.message) {
      return d.message;
    }
    if (d && d.detail) {
      return d.detail;
    }
    if (d && d.error) {
      return d.error;
    }
    return 'Something went wrong. Please try again.';
  }

  function button(label, className, onClick) {
    const node = el('button', label, className);
    node.type = 'button';
    node.addEventListener('click', function () { onClick(node); });
    return node;
  }

  // Run one action (a click), show the result for a few seconds, and draw the page again.
  async function act(method, path, body, okText) {
    busy = true;
    const reply = await STAFF.call(method, path, body);
    busy = false;
    if (reply.status >= 200 && reply.status < 300) {
      say(notice, okText);
    } else if (reply.status === 403) {
      say(notice, 'You are not allowed to do this.');
    } else {
      say(notice, problem(reply));
    }
    setTimeout(function () { say(notice, ''); }, 5000);
    refresh();
  }

  function drawAlerts(alerts) {
    alertsEl.replaceChildren();
    if (!alerts.length) {
      return;
    }
    alertsEl.appendChild(el('h2', 'Customers who rang (' + alerts.length + ')'));
    alerts.forEach(function (a) {
      const card = el('div', null, 'alert-card');
      card.appendChild(el('strong', 'Table ' + a.table));
      card.appendChild(el('span', 'order ' + a.order_id + ' has waited ' +
        a.minutes_waiting + ' min (' + a.order_status + ')'));
      card.appendChild(button('Attended', 'primary small', function (node) {
        node.disabled = true;
        act('POST', '/kitchen/alerts/' + a.alert_id + '/attend/', undefined, 'Marked as attended.');
      }));
      alertsEl.appendChild(card);
    });
  }

  function drawWaiters(waiters) {
    waitersEl.replaceChildren();
    waitersEl.appendChild(el('h2', 'Waiters'));
    if (!waiters.length) {
      waitersEl.appendChild(el('p', 'No waiters yet. The admin adds them in the Staff section.', 'muted'));
      return;
    }
    const row = el('div', null, 'row');
    waiters.forEach(function (w) {
      row.appendChild(el('span', w.username + ': ' + (STATE_WORDS[w.state] || w.state), 'badge ' + w.state));
    });
    waitersEl.appendChild(row);
  }

  function orderCard(order, freeWaiters) {
    const card = el('section', null, 'order-card');

    const title = el('h2');
    title.appendChild(el('span', 'Table ' + order.table + ' - order ' + order.order_id));
    title.appendChild(el('span', minutesAgo(order.created_at) + ' min ago, ' +
      order.persons + ' person(s)', 'muted'));
    card.appendChild(title);

    const list = el('ul');
    order.items.forEach(function (item) {
      list.appendChild(el('li', item.quantity + ' x ' + item.name));
    });
    card.appendChild(list);

    if (order.status === 'placed') {
      card.appendChild(button('Start preparing', 'primary', function (node) {
        node.disabled = true;
        act('POST', '/kitchen/orders/' + order.order_id + '/status/',
          { status: 'preparing' }, 'Order ' + order.order_id + ' is being prepared.');
      }));
    } else if (order.status === 'preparing') {
      card.appendChild(button('Mark ready', 'primary', function (node) {
        node.disabled = true;
        act('POST', '/kitchen/orders/' + order.order_id + '/status/',
          { status: 'ready' }, 'Order ' + order.order_id + ' is ready.');
      }));
    } else if (order.status === 'ready') {
      if (order.waiter) {
        card.appendChild(el('p', 'Given to ' + order.waiter + '. Waiting for the waiter to serve.', 'muted'));
      } else if (!freeWaiters.length) {
        card.appendChild(el('p', 'No free waiter right now.', 'muted'));
      } else {
        card.appendChild(el('p', 'Give to:', 'muted'));
        const row = el('div', null, 'row');
        freeWaiters.forEach(function (w) {
          row.appendChild(button(w.username, 'primary small', function (node) {
            node.disabled = true;
            act('POST', '/kitchen/orders/' + order.order_id + '/assign/',
              { waiter: w.id }, 'Given to ' + w.username + '.');
          }));
        });
        card.appendChild(row);
      }
    }
    return card;
  }

  function drawOrders(orders, waiters) {
    ordersEl.replaceChildren();
    const free = waiters.filter(function (w) { return w.state === 'free'; });
    GROUPS.forEach(function (group) {
      const rows = orders.filter(function (o) { return o.status === group.status; });
      ordersEl.appendChild(el('h2', group.title + ' (' + rows.length + ')'));
      if (!rows.length) {
        ordersEl.appendChild(el('p', 'Nothing here.', 'muted'));
      }
      rows.forEach(function (o) { ordersEl.appendChild(orderCard(o, free)); });
    });
  }

  async function refresh() {
    if (busy) {
      return;
    }
    const results = await Promise.all([
      STAFF.call('GET', '/kitchen/orders/'),
      STAFF.call('GET', '/kitchen/waiters/'),
      STAFF.call('GET', '/kitchen/alerts/')
    ]);
    const orders = results[0];
    const waiters = results[1];
    const alerts = results[2];
    if (orders.status !== 200 || waiters.status !== 200 || alerts.status !== 200) {
      say(notice, 'The kitchen data could not be loaded.');
      return;
    }
    drawAlerts(alerts.data);
    drawWaiters(waiters.data);
    drawOrders(orders.data, waiters.data);
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();