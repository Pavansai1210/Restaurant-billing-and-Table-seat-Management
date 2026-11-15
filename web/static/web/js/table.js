(function () {
  const app = document.getElementById('app');
  const table = Number(app.dataset.table);
  const KEY = 'rms_group_' + table;          // the group token of this phone for this table
  const HOLD_KEY = 'rms_hold_' + table;      // when the 5-minute hold of this phone ends

  const seatInfo = document.getElementById('seat-info');
  const seatBox = document.getElementById('seat-box');
  const menuBox = document.getElementById('menu-box');
  const personsEl = document.getElementById('persons');
  const okButton = document.getElementById('ok');
  const seatMessage = document.getElementById('seat-message');
  const suggestions = document.getElementById('suggestions');
  const holdNote = document.getElementById('hold-note');
  const menuEl = document.getElementById('menu');
  const cartSummary = document.getElementById('cart-summary');
  const placeButton = document.getElementById('place');
  const orderMessage = document.getElementById('order-message');

  const MAX_PERSONS = 30;
  const MAX_PER_ITEM = 20;
  let persons = 1;
  let menuLoaded = false;
  const items = {};      // menu item id -> item
  const cart = {};       // menu item id -> quantity

  async function loadSeats() {
    const reply = await api('GET', '/tables/' + table + '/');
    if (reply.status !== 200) {
      seatInfo.textContent = 'This table was not found.';
      return false;
    }
    const d = reply.data;
    seatInfo.textContent = 'Table ' + d.table + ': ' + d.free_seats + ' of ' + d.capacity + ' seats are free.';
    return true;
  }

  function drawPersons() {
    personsEl.textContent = persons;
  }

  document.getElementById('minus').addEventListener('click', function () {
    if (persons > 1) {
      persons--;
      drawPersons();
    }
  });

  document.getElementById('plus').addEventListener('click', function () {
    if (persons < MAX_PERSONS) {
      persons++;
      drawPersons();
    }
  });

  // ----- the 5-minute hold -----
  function holdLeft() {
    const until = Number(localStorage.getItem(HOLD_KEY));
    if (!until) {
      return null;
    }
    return Math.max(0, Math.round((until - Date.now()) / 1000));
  }

  function drawHold() {
    const left = holdLeft();
    if (left === null) {
      say(holdNote, '');
      return;
    }
    const minutes = Math.floor(left / 60);
    const rest = String(left % 60).padStart(2, '0');
    say(holdNote, 'Your seats are held for ' + minutes + ':' + rest + '. Place an order to keep them.');
  }

  async function checkHold() {
    const left = holdLeft();
    if (left === null) {
      return;
    }
    if (left === 0) {
      localStorage.removeItem(KEY);
      localStorage.removeItem(HOLD_KEY);
      Object.keys(cart).forEach(function (id) { delete cart[id]; });
      menuLoaded = false;
      drawCart();
      await init();
      say(seatMessage, 'Your hold has ended. Please choose your seats again.');
      return;
    }
    drawHold();
  }

  // ----- other tables -----
  async function holdAt(other, node) {
    node.disabled = true;
    const reply = await api('POST', '/groups/hold/', { table: other, persons: persons });
    if (reply.status === 201) {
      localStorage.setItem('rms_group_' + other, reply.data.token);
      localStorage.setItem('rms_hold_' + other, String(Date.now() + reply.data.hold_seconds * 1000));
      window.location.href = '/table/' + other + '/';
      return;
    }
    node.disabled = false;
    if (reply.status === 409) {
      say(seatMessage, reply.data.message);
      drawSuggestions(reply.data.suggestions);
    } else {
      say(seatMessage, 'Something went wrong. Please try again.');
    }
  }

  function drawSuggestions(list) {
    suggestions.replaceChildren();
    (list || []).forEach(function (s) {
      const row = el('li', 'Table ' + s.table + ' has ' + s.free_seats + ' free seats ');
      const take = el('button', 'Take seats here', 'primary small');
      take.type = 'button';
      take.addEventListener('click', function () { holdAt(s.table, take); });
      row.appendChild(take);
      suggestions.appendChild(row);
    });
  }

  okButton.addEventListener('click', async function () {
    okButton.disabled = true;                 // stops a double click from making two groups
    say(seatMessage, '');
    suggestions.replaceChildren();
    const reply = await api('POST', '/groups/', { table: table, persons: persons });
    okButton.disabled = false;

    if (reply.status === 201) {
      localStorage.setItem(KEY, reply.data.token);
      localStorage.removeItem(HOLD_KEY);
      await loadSeats();
      await showMenu();
    } else if (reply.status === 409) {
      say(seatMessage, reply.data.message);
      drawSuggestions(reply.data.suggestions);
      await loadSeats();
    } else {
      say(seatMessage, 'Something went wrong. Please try again.');
    }
  });

  // ----- menu and cart -----
  function menuRow(item) {
    const row = el('div', null, 'item');
    const left = el('div', null, 'item-left');
    if (item.image) {
      const picture = document.createElement('img');
      picture.src = item.image;
      picture.alt = item.name;
      picture.width = 64;
      picture.height = 64;
      picture.className = 'thumb';
      left.appendChild(picture);
    }
    const info = el('div');
    info.appendChild(el('strong', item.name));
    info.appendChild(el('div', (item.is_veg ? 'Veg' : 'Non-veg') + ' - ' + money(item.price), 'muted'));
    left.appendChild(info);
    row.appendChild(left);

    const stepper = el('div', null, 'stepper');
    const minus = el('button', '-');
    const qty = el('span', '0');
    const plus = el('button', '+');
    minus.type = 'button';
    plus.type = 'button';
    minus.addEventListener('click', function () { change(item.id, -1, qty); });
    plus.addEventListener('click', function () { change(item.id, 1, qty); });
    stepper.append(minus, qty, plus);
    row.appendChild(stepper);
    return row;
  }

  function change(id, step, qtyEl) {
    const next = Math.min(MAX_PER_ITEM, Math.max(0, (cart[id] || 0) + step));
    if (next === 0) {
      delete cart[id];
    } else {
      cart[id] = next;
    }
    qtyEl.textContent = next;
    drawCart();
  }

  function drawCart() {
    let count = 0;
    let total = 0;
    Object.keys(cart).forEach(function (id) {
      count += cart[id];
      total += cart[id] * Number(items[id].price);
    });
    cartSummary.textContent = count ? count + ' item(s), about ' + money(total) : 'Nothing selected';
    placeButton.disabled = count === 0;
  }

  async function showMenu() {
    seatBox.hidden = true;
    menuBox.hidden = false;
    document.getElementById('my-orders').href = '/table/' + table + '/orders/';
    drawHold();
    if (menuLoaded) {
      return;
    }
    const reply = await api('GET', '/menu/');
    if (reply.status !== 200) {
      say(orderMessage, 'The menu could not be loaded.');
      return;
    }
    menuLoaded = true;
    menuEl.replaceChildren();
    reply.data.forEach(function (group) {
      menuEl.appendChild(el('h3', group.category));
      group.items.forEach(function (item) {
        items[item.id] = item;
        menuEl.appendChild(menuRow(item));
      });
    });
  }

  placeButton.addEventListener('click', async function () {
    say(orderMessage, '');
    placeButton.disabled = true;
    const token = localStorage.getItem(KEY);
    const lines = Object.keys(cart).map(function (id) {
      return { menu_item: Number(id), quantity: cart[id] };
    });
    const reply = await api('POST', '/orders/', { token: token, items: lines });

    if (reply.status === 201) {
      localStorage.removeItem(HOLD_KEY);      // the order confirmed the hold
      window.location.href = '/table/' + table + '/orders/';
      return;
    }

    const closed = reply.status === 404 || reply.status === 410 ||
      (reply.status === 409 && reply.data && reply.data.error === 'group_closed');
    if (closed) {
      localStorage.removeItem(KEY);
      localStorage.removeItem(HOLD_KEY);
      Object.keys(cart).forEach(function (id) { delete cart[id]; });
      menuLoaded = false;
      drawCart();
      await init();
      say(seatMessage, 'Your seats are no longer valid. Please choose your seats again.');
      return;
    }

    say(orderMessage, (reply.data && reply.data.message) || 'Something went wrong. Please try again.');
    drawCart();
  });

    async function init() {
    const found = await loadSeats();
    if (!found) {
      return;
    }
    const token = localStorage.getItem(KEY);
    if (token) {
      // Ask the server if this group still has its seats. If not, forget the old token.
      const check = await api('GET', '/group/orders/?token=' + encodeURIComponent(token));
      const alive = check.status === 200 &&
        (check.data.status === 'seated' || check.data.status === 'held');
      if (!alive) {
        localStorage.removeItem(KEY);
        localStorage.removeItem(HOLD_KEY);
      }
    }
    if (localStorage.getItem(KEY)) {
      await showMenu();
    } else {
      menuBox.hidden = true;
      seatBox.hidden = false;
    }
  }

  drawPersons();
  init();
  setInterval(checkHold, 1000);
  setInterval(loadSeats, 5000);       // keep the seat number fresh while the page is open
})();