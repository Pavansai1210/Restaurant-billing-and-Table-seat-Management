(function () {
  const app = document.getElementById('app');
  const table = Number(app.dataset.table);
  const token = localStorage.getItem('rms_group_' + table);

  const stateEl = document.getElementById('state');
  const notice = document.getElementById('notice');
  const ordersEl = document.getElementById('orders');
  const billBox = document.getElementById('bill');
  const billTotal = document.getElementById('bill-total');

  document.getElementById('more').href = '/table/' + table + '/';
    document.getElementById('bill-link').href = '/table/' + table + '/bill/';

  const WORDS = {
    placed: 'Order placed',
    preparing: 'Being prepared',
    ready: 'Ready, on its way to your table',
    served: 'Served. Enjoy your meal!',
    cancelled: 'Cancelled'
  };

  let left = {};          // order id -> seconds left to change that order
  let notes = {};         // order id -> the line that shows the countdown
  const dismissed = {};   // order id -> true when the customer said No to ringing

  function noteText(seconds) {
    if (seconds <= 0) {
      return 'This order can no longer be changed.';
    }
    const minutes = Math.floor(seconds / 60);
    const rest = String(seconds % 60).padStart(2, '0');
    return 'You can still change this order for ' + minutes + ':' + rest + '.';
  }

  function button(label, className, onClick) {
    const node = el('button', label, className);
    node.type = 'button';
    node.addEventListener('click', function () { onClick(node); });
    return node;
  }

  async function addItem(order, item, node) {
    node.disabled = true;
    const reply = await api('POST', '/orders/' + order.id + '/items/' + item.id + '/add/', { token: token });
    if (reply.status === 200) {
      say(notice, 'One more was added.');
    } else if (reply.status === 403) {
      say(notice, 'It is too late to change this order.');
    } else {
      say(notice, (reply.data && reply.data.message) || 'Could not add it. Please try again.');
    }
    refresh();
  }

  async function removeItem(order, item, quantity, node) {
    node.disabled = true;
    const body = { token: token };
    if (quantity) {
      body.quantity = quantity;
    }
    const reply = await api('POST', '/orders/' + order.id + '/items/' + item.id + '/remove/', body);
    if (reply.status === 200) {
      say(notice, reply.data.status === 'cancelled'
        ? 'Order ' + order.id + ' was cancelled, because no food was left in it.'
        : 'The food was removed.');
    } else if (reply.status === 403) {
      say(notice, 'It is too late to change this order.');
    } else {
      say(notice, 'Could not remove it. Please try again.');
    }
    refresh();
  }

  async function cancelOrder(order, node) {
    if (!window.confirm('Cancel the whole of order ' + order.id + '?')) {
      return;
    }
    node.disabled = true;
    const reply = await api('POST', '/orders/' + order.id + '/cancel/', { token: token });
    if (reply.status === 200) {
      say(notice, 'Order ' + order.id + ' was cancelled.');
    } else if (reply.status === 403) {
      say(notice, 'It is too late to cancel this order.');
    } else {
      say(notice, 'Could not cancel. Please try again.');
    }
    refresh();
  }

  async function ringKitchen(order) {
    const reply = await api('POST', '/orders/' + order.id + '/ring/', { token: token });
    if (reply.status === 201) {
      say(notice, 'The kitchen knows. Thank you for waiting.');
    } else if (reply.status === 409) {
      say(notice, (reply.data && reply.data.message) || 'Please wait a little.');
    } else {
      say(notice, 'Could not send the message. Please try again.');
    }
    refresh();
  }

  function itemRow(order, item, open) {
    const row = el('li', item.quantity + ' x ' + item.name + ' - ' + money(item.price * item.quantity));
    if (open) {
      row.appendChild(button('Add 1', 'primary small', function (node) {
        addItem(order, item, node);
      }));
      row.appendChild(button('Remove 1', 'danger small', function (node) {
        removeItem(order, item, 1, node);
      }));
      if (item.quantity > 1) {
        row.appendChild(button('Remove all', 'danger small', function (node) {
          removeItem(order, item, 0, node);
        }));
      }
    }
    return row;
  }

  function ringBox(order) {
    const box = el('div', null, 'ring');
    box.appendChild(el('p', 'This order is taking more time than usual. Do you want to ring for attention?'));
    box.appendChild(button('Yes, ring', 'primary', function () { ringKitchen(order); }));
    box.appendChild(button('No', 'danger', function () {
      dismissed[order.id] = true;
      box.hidden = true;
    }));
    return box;
  }

  function orderCard(order) {
    const card = el('section', null, 'order-card' + (order.status === 'cancelled' ? ' cancelled' : ''));

    const title = el('h2');
    title.appendChild(el('span', 'Order ' + order.id));
    title.appendChild(el('span', WORDS[order.status] || order.status, 'muted'));
    card.appendChild(title);

    const open = order.edit_seconds_left > 0;
    const list = el('ul');
    order.items.forEach(function (item) { list.appendChild(itemRow(order, item, open)); });
    if (!order.items.length) {
      list.appendChild(el('li', 'No food left in this order.'));
    }
    card.appendChild(list);
    card.appendChild(el('p', 'Order total: ' + money(order.total)));

    if (order.status === 'cancelled' && order.cancel_reason === 'visit_closed') {
      card.appendChild(el('p', 'The visit was closed before this was served. You are not charged.', 'muted'));
    }

    if (order.status !== 'cancelled') {
      const note = el('p', noteText(order.edit_seconds_left), 'muted');
      notes[order.id] = note;
      card.appendChild(note);
    }
    if (open) {
      card.appendChild(button('Cancel whole order', 'danger', function (node) {
        cancelOrder(order, node);
      }));
    }
    if (order.ring_wait_seconds === 0 && !dismissed[order.id]) {
      card.appendChild(ringBox(order));
    }
    return card;
  }

  async function refresh() {
    if (!token) {
      say(stateEl, 'You have no seats at this table yet. Choose your seats first.');
      return;
    }
    const reply = await api('GET', '/group/orders/?token=' + encodeURIComponent(token));
    if (reply.status !== 200) {
      ordersEl.replaceChildren();
      billBox.hidden = true;
      say(stateEl, 'We could not find your seats. Please choose them again.');
      return;
    }
    const d = reply.data;
    left = {};
    notes = {};
    ordersEl.replaceChildren();
    d.orders.forEach(function (order) {
      left[order.id] = order.edit_seconds_left;
      ordersEl.appendChild(orderCard(order));
    });
    say(stateEl, d.orders.length ? '' : 'You have not ordered anything yet.');
    billBox.hidden = d.orders.length === 0;
    billTotal.textContent = money(d.bill_total);
  }

  setInterval(function () {
    let closed = false;
    Object.keys(left).forEach(function (id) {
      if (left[id] > 0) {
        left[id]--;
        if (notes[id]) {
          notes[id].textContent = noteText(left[id]);
        }
        if (left[id] === 0) {
          closed = true;
        }
      }
    });
    if (closed) {
      refresh();      // the time is over: draw the card again without the buttons
    }
  }, 1000);

  refresh();
  setInterval(refresh, 5000);
})();