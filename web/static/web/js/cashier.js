(function () {
  const me = STAFF.require('cashier', 'admin');
  if (!me) {
    return;
  }

  const notice = document.getElementById('notice');
  const stateEl = document.getElementById('state');
  const listEl = document.getElementById('requests');
  const visitsEl = document.getElementById('visits');
  const visitsState = document.getElementById('visits-state');
  const unpaidEl = document.getElementById('unpaid');
  const unpaidState = document.getElementById('unpaid-state');

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

  async function closeUnpaid(row, node) {
    const sure = Number(row.total) > 0
      ? 'Table ' + row.table + ' left WITHOUT paying ' + money(row.total) +
        '. Close this visit as unpaid? The seats become free and the amount stays on record.'
      : 'Table ' + row.table + ' was not served any food. Close this visit? ' +
        'The seats become free and nothing is owed.';
    if (!window.confirm(sure)) {
      return;
    }
    node.disabled = true;
    busy = true;
    const reply = await STAFF.call('POST', '/cashier/visits/' + row.group_id + '/close-unpaid/');
    busy = false;
    if (reply.status === 200) {
      say(notice, reply.data.state === 'closed'
        ? 'Table ' + row.table + ' closed. Nothing was served, so nothing is owed.'
        : 'Table ' + row.table + ' closed as unpaid (' + money(reply.data.total) + ').');
    } else {
      say(notice, (reply.data && reply.data.message) || 'Could not close. Please try again.');
    }
    setTimeout(function () { say(notice, ''); }, 5000);
    refresh();
  }

  function visitCard(row) {
    const box = el('section', null, 'order-card');
    const title = el('h2');
    title.appendChild(el('span', 'Table ' + row.table));
    title.appendChild(el('span', 'seated ' + minutesAgo(row.since) + ' min ago', 'muted'));
    box.appendChild(title);
    box.appendChild(el('p', row.persons + ' person(s)'));
    const total = el('p', 'Served food so far: ');
    total.appendChild(el('strong', money(row.total)));
    box.appendChild(total);
    const button = el('button', 'Close unpaid', 'danger');
    button.type = 'button';
    button.addEventListener('click', function () { closeUnpaid(row, button); });
    box.appendChild(button);
    return box;
  }

  async function settle(row, node) {
    if (!window.confirm('Did you receive ' + money(row.total) + ' from table ' + row.table + '?')) {
      return;
    }
    node.disabled = true;
    busy = true;
    const reply = await STAFF.call('POST', '/cashier/unpaid/' + row.bill_id + '/settle/');
    busy = false;
    if (reply.status === 200) {
      say(notice, 'Table ' + row.table + ' paid ' + money(reply.data.total) +
        '. The receipt is ready for the gate.');
    } else {
      say(notice, (reply.data && reply.data.message) || 'Could not save. Please try again.');
    }
    setTimeout(function () { say(notice, ''); }, 5000);
    refresh();
  }

  function unpaidCard(row) {
    const box = el('section', null, 'order-card');
    const title = el('h2');
    title.appendChild(el('span', 'Table ' + row.table));
    title.appendChild(el('span', 'left ' + minutesAgo(row.since) + ' min ago', 'muted'));
    box.appendChild(title);
    box.appendChild(el('p', row.persons + ' person(s)'));
    const total = el('p', 'Owes: ');
    total.appendChild(el('strong', money(row.total)));
    box.appendChild(total);
    const button = el('button', 'Cash received', 'primary');
    button.type = 'button';
    button.addEventListener('click', function () { settle(row, button); });
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

    const visits = await STAFF.call('GET', '/cashier/visits/');
    if (visits.status === 200) {
      visitsEl.replaceChildren();
      visits.data.forEach(function (row) { visitsEl.appendChild(visitCard(row)); });
      say(visitsState, visits.data.length
        ? 'Seated groups: ' + visits.data.length
        : 'No active visits.');
    }

    const unpaid = await STAFF.call('GET', '/cashier/unpaid/');
    if (unpaid.status === 200) {
      unpaidEl.replaceChildren();
      unpaid.data.forEach(function (row) { unpaidEl.appendChild(unpaidCard(row)); });
      say(unpaidState, unpaid.data.length
        ? 'Bills not paid yet: ' + unpaid.data.length
        : 'No unpaid bills.');
    }
  }

  refresh();
  setInterval(refresh, 4000);
})();