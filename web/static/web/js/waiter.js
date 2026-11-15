(function () {
  const me = STAFF.require('waiter', 'admin');
  if (!me) {
    return;
  }

  const notice = document.getElementById('notice');
  const stateEl = document.getElementById('state');
  const ordersEl = document.getElementById('orders');
  const isAdmin = me.role === 'admin';

  document.getElementById('who').textContent = 'Logged in as ' + me.username + ' (' + me.role + ')';
  document.getElementById('logout').addEventListener('click', STAFF.logout);
  if (isAdmin) {
    document.getElementById('to-panel').hidden = false;
  }

  const REFRESH_MS = 4000;
  let busy = false;

  function button(label, className, onClick) {
    const node = el('button', label, className);
    node.type = 'button';
    node.addEventListener('click', function () { onClick(node); });
    return node;
  }

  async function served(order, node) {
    node.disabled = true;
    busy = true;
    const reply = await STAFF.call('POST', '/waiter/orders/' + order.order_id + '/served/');
    busy = false;
    if (reply.status === 200) {
      say(notice, 'Order ' + order.order_id + ' for table ' + order.table + ' is served.');
    } else if (reply.status === 404) {
      say(notice, 'This order is not yours any more.');
    } else {
      say(notice, (reply.data && reply.data.message) || 'Could not save. Please try again.');
    }
    setTimeout(function () { say(notice, ''); }, 5000);
    refresh();
  }

  function card(order) {
    const box = el('section', null, 'order-card');
    const title = el('h2');
    title.appendChild(el('span', 'Table ' + order.table));
    title.appendChild(el('span', 'order ' + order.order_id, 'muted'));
    box.appendChild(title);

    const list = el('ul');
    order.items.forEach(function (item) {
      list.appendChild(el('li', item.quantity + ' x ' + item.name));
    });
    box.appendChild(list);

    if (isAdmin) {
      box.appendChild(el('p', order.waiter ? 'Given to ' + order.waiter : 'No waiter chosen yet', 'muted'));
    } else {
      box.appendChild(button('Served', 'primary', function (node) { served(order, node); }));
    }
    return box;
  }

  async function refresh() {
    if (busy) {
      return;
    }
    const path = isAdmin ? '/waiter/all/' : '/waiter/orders/';
    const reply = await STAFF.call('GET', path);
    if (reply.status !== 200) {
      say(notice, 'The orders could not be loaded.');
      return;
    }
    ordersEl.replaceChildren();
    reply.data.forEach(function (order) { ordersEl.appendChild(card(order)); });
    say(stateEl, reply.data.length
      ? 'Orders to serve: ' + reply.data.length
      : 'Nothing to serve right now.');
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();