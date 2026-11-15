(function () {
  const me = STAFF.require('cashier', 'admin');
  if (!me) {
    return;
  }

  const notice = document.getElementById('notice');
  const stateEl = document.getElementById('state');
  const listEl = document.getElementById('requests');

  document.getElementById('who').textContent = 'Logged in as ' + me.username + ' (' + me.role + ')';
  document.getElementById('logout').addEventListener('click', STAFF.logout);
  if (me.role === 'admin') {
    document.getElementById('to-panel').hidden = false;
  }

  let busy = false;

  function minutesAgo(text) {
    return Math.max(0, Math.floor((Date.now() - new Date(text).getTime()) / 60000));
  }

  async function received(row, node) {
    if (!window.confirm('Did you receive ' + money(row.total) + ' from table ' + row.table + '?')) {
      return;
    }
    node.disabled = true;
    busy = true;
    const reply = await STAFF.call('POST', '/cashier/requests/' + row.bill_id + '/received/');
    busy = false;
    if (reply.status === 200) {
      say(notice, 'Table ' + row.table + ' paid ' + money(reply.data.total) + '.');
    } else {
      say(notice, (reply.data && reply.data.message) || 'Could not save. Please try again.');
    }
    setTimeout(function () { say(notice, ''); }, 5000);
    refresh();
  }

  function card(row) {
    const box = el('section', null, 'order-card');
    const title = el('h2');
    title.appendChild(el('span', 'Table ' + row.table));
    title.appendChild(el('span', 'asked ' + minutesAgo(row.asked_at) + ' min ago', 'muted'));
    box.appendChild(title);
    box.appendChild(el('p', row.persons + ' person(s)'));
    const total = el('p', 'Collect: ');
    total.appendChild(el('strong', money(row.total)));
    box.appendChild(total);
    const button = el('button', 'Cash received', 'primary');
    button.type = 'button';
    button.addEventListener('click', function () { received(row, button); });
    box.appendChild(button);
    return box;
  }

  async function refresh() {
    if (busy) {
      return;
    }
    const reply = await STAFF.call('GET', '/cashier/requests/');
    if (reply.status !== 200) {
      say(notice, 'The requests could not be loaded.');
      return;
    }
    listEl.replaceChildren();
    reply.data.forEach(function (row) { listEl.appendChild(card(row)); });
    say(stateEl, reply.data.length
      ? 'Customers waiting to pay cash: ' + reply.data.length
      : 'No cash requests right now.');
  }

  refresh();
  setInterval(refresh, 4000);
})();