(function () {
  const me = STAFF.require('admin');
  if (!me) {
    return;
  }

  const section = document.getElementById('panel').dataset.section;
  const content = document.getElementById('content');
  const notice = document.getElementById('notice');

  document.getElementById('who').textContent = 'Logged in as ' + me.username + ' (admin)';
  document.getElementById('logout').addEventListener('click', STAFF.logout);
  document.querySelectorAll('.tabs a').forEach(function (link) {
    link.className = link.dataset.tab === section ? 'active' : '';
  });

  // ---------- small helpers ----------
  function button(label, className, onClick) {
    const node = el('button', label, className);
    node.type = 'button';
    node.addEventListener('click', function () { onClick(node); });
    return node;
  }

  function field(type, value, placeholder) {
    const node = document.createElement('input');
    node.type = type;
    if (value !== undefined && value !== null) {
      node.value = value;
    }
    if (placeholder) {
      node.placeholder = placeholder;
    }
    return node;
  }

  function checkbox(checked) {
    const node = document.createElement('input');
    node.type = 'checkbox';
    node.checked = !!checked;
    return node;
  }

  function select(options, current) {
    const node = document.createElement('select');
    options.forEach(function (option) {
      const entry = document.createElement('option');
      entry.value = option.value;
      entry.textContent = option.label;
      node.appendChild(entry);
    });
    node.value = current;
    return node;
  }

  function labelled(text, control) {
    const wrap = el('label', text + ' ');
    wrap.appendChild(control);
    return wrap;
  }

  // Turn an API error into a sentence a person can read.
  function problem(reply) {
    const d = reply.data;
    if (!d) {
      return 'Something went wrong. Please try again.';
    }
    if (d.message) {
      return d.message;
    }
    if (d.detail) {
      return d.detail;
    }
    const parts = [];
    Object.keys(d).forEach(function (key) {
      const value = Array.isArray(d[key]) ? d[key].join(' ') : String(d[key]);
      parts.push(key + ': ' + value);
    });
    return parts.length ? parts.join(' | ') : 'Something went wrong. Please try again.';
  }

  // Run an API call, show the result as a message, and draw the page again.
  async function act(method, path, body, okText, again) {
    const reply = await STAFF.call(method, path, body);
    if (reply.status >= 200 && reply.status < 300) {
      say(notice, okText);
    } else if (reply.status === 403) {
      say(notice, 'You are not allowed to do this.');
    } else {
      say(notice, problem(reply));
    }
    if (again) {
      again();
    }
    return reply;
  }

  function addRow(table, cells) {
    const row = document.createElement('tr');
    cells.forEach(function (cell) {
      const td = document.createElement('td');
      if (cell instanceof Node) {
        td.appendChild(cell);
      } else {
        td.textContent = cell === null || cell === undefined ? '' : cell;
      }
      row.appendChild(td);
    });
    table.appendChild(row);
  }

  function makeTable(headings) {
    const wrap = el('div', null, 'scroll');
    const table = el('table', null, 'list');
    const head = document.createElement('tr');
    headings.forEach(function (text) { head.appendChild(el('th', text)); });
    table.appendChild(head);
    wrap.appendChild(table);
    return { wrap: wrap, table: table };
  }

  function when(text) {
    return text ? new Date(text).toLocaleString() : '';
  }

  // ---------- Home ----------
  function drawHome() {
    content.replaceChildren();
    content.appendChild(el('h1', 'Admin'));
    content.appendChild(el('p', 'Choose a section above to manage the restaurant.', 'muted'));
    const list = el('ul');
    [
      'Menu: food categories and items, prices, hide or show a food',
      'Tables: seats of each table, switch a table off',
      'Staff: add staff, change a role, reset a password, switch a person off',
      'Settings: how long before a customer may ring the kitchen',
      'Orders: see orders and groups (read only)',
      'Audit log: who changed what, and when'
    ].forEach(function (text) { list.appendChild(el('li', text)); });
    content.appendChild(list);
  }

  // ---------- Menu ----------
  async function drawMenu() {
    const cats = await STAFF.call('GET', '/admin/categories/');
    const items = await STAFF.call('GET', '/admin/menu-items/');
    if (cats.status !== 200 || items.status !== 200) {
      say(notice, 'The menu could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Menu'));

    // categories
    content.appendChild(el('h2', 'Categories'));
    const addCat = el('div', null, 'row');
    const catName = field('text', '', 'New category');
    addCat.append(catName, button('Add category', 'primary', function () {
      act('POST', '/admin/categories/', { name: catName.value.trim() }, 'Category added.', drawMenu);
    }));
    content.appendChild(addCat);

    cats.data.forEach(function (cat) {
      const row = el('div', null, 'row');
      const name = field('text', cat.name);
      row.append(
        name,
        button('Save name', 'danger small', function () {
          act('PATCH', '/admin/categories/' + cat.id + '/', { name: name.value.trim() }, 'Category saved.', drawMenu);
        }),
        button('Delete', 'danger small', function () {
          if (window.confirm('Delete the category "' + cat.name + '"?')) {
            act('DELETE', '/admin/categories/' + cat.id + '/', undefined, 'Category deleted.', drawMenu);
          }
        })
      );
      content.appendChild(row);
    });

    // new food
    content.appendChild(el('h2', 'Add a food item'));
    const form = el('div', null, 'card');
    const category = select(cats.data.map(function (c) { return { value: c.id, label: c.name }; }),
      cats.data.length ? cats.data[0].id : '');
    const foodName = field('text', '', 'Name');
    const price = field('number', '', 'Price');
    price.step = '0.01';
    price.min = '0';
    const veg = checkbox(true);
    form.append(
      labelled('Category', category), labelled('Name', foodName), labelled('Price', price),
      labelled('Veg', veg),
      button('Add food', 'primary', function () {
        act('POST', '/admin/menu-items/', {
          category: Number(category.value),
          name: foodName.value.trim(),
          price: price.value,
          is_veg: veg.checked
        }, 'Food added.', drawMenu);
      })
    );
    content.appendChild(form);

    // all food
    content.appendChild(el('h2', 'Food items'));
    const t = makeTable(['Photo', 'Name', 'Category', 'Price', 'Veg', 'Available', '']);
    const names = {};
    cats.data.forEach(function (c) { names[c.id] = c.name; });
    items.data.forEach(function (item) {
      const newPrice = field('number', item.price);
      newPrice.step = '0.01';
      newPrice.min = '0';
      const available = checkbox(item.is_available);
      const veg2 = checkbox(item.is_veg);

      const photoCell = el('div');
      if (item.image) {
        const small = document.createElement('img');
        small.src = item.image;
        small.alt = item.name;
        small.width = 60;
        small.height = 60;
        small.className = 'thumb';
        photoCell.appendChild(small);
      }
      const choose = document.createElement('input');
      choose.type = 'file';
      choose.accept = 'image/*';
      choose.addEventListener('change', async function () {
        if (!choose.files.length) {
          return;
        }
        const data = new FormData();
        data.append('image', choose.files[0]);
        const done = await STAFF.upload('/admin/menu-items/' + item.id + '/photo/', data);
        say(notice, done.status === 200 ? 'Photo saved.' : problem(done));
        drawMenu();
      });
      photoCell.appendChild(choose);
      if (item.image) {
        photoCell.appendChild(button('Remove photo', 'danger small', function () {
          act('DELETE', '/admin/menu-items/' + item.id + '/photo/', undefined, 'Photo removed.', drawMenu);
        }));
      }

      const actions = el('div', null, 'row');
      actions.append(
        button('Save', 'primary small', function () {
          act('PATCH', '/admin/menu-items/' + item.id + '/', {
            price: newPrice.value, is_available: available.checked, is_veg: veg2.checked
          }, 'Food saved.', drawMenu);
        }),
        button('Delete', 'danger small', function () {
          if (window.confirm('Delete "' + item.name + '"? If it is in old orders, hide it instead.')) {
            act('DELETE', '/admin/menu-items/' + item.id + '/', undefined, 'Food deleted.', drawMenu);
          }
        })
      );
      addRow(t.table, [photoCell, item.name, names[item.category] || '', newPrice, veg2, available, actions]);
    });
    content.appendChild(t.wrap);
  }

  // ---------- Tables ----------

    async function drawTables() {
    const reply = await STAFF.call('GET', '/admin/tables/');
    if (reply.status !== 200) {
      say(notice, 'The tables could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Tables', 'no-print'));

    const form = el('div', null, 'card no-print');
    const number = field('number', '', 'Number');
    number.min = '1';
    const capacity = field('number', '', 'Seats');
    capacity.min = '1';
    form.append(
      labelled('Table number', number), labelled('Seats', capacity),
      button('Add table', 'primary', function () {
        act('POST', '/admin/tables/', {
          number: Number(number.value), capacity: Number(capacity.value)
        }, 'Table added.', drawTables);
      })
    );
    content.appendChild(form);

    // ----- QR codes -----
    const qrBox = el('div', null, 'card no-print');
    const qrNote = el('p', '', 'muted');
    const qrGrid = el('div', null, 'qr-grid');

    async function showQr(node) {
      node.disabled = true;
      const r = await STAFF.call('GET', '/admin/tables/qr/');
      node.disabled = false;
      if (r.status !== 200) {
        say(notice, 'The QR codes could not be loaded.');
        return;
      }
      qrGrid.replaceChildren();
      r.data.tables.forEach(function (t) {
        const card = el('div', null, 'qr-card');
        card.appendChild(el('h2', 'Table ' + t.table));
        const picture = document.createElement('img');
        picture.src = t.image;               // a picture made by our own server
        picture.alt = 'QR code for table ' + t.table;
        picture.width = 200;
        picture.height = 200;
        card.appendChild(picture);
        card.appendChild(el('p', 'Scan to order'));
        card.appendChild(el('p', t.url, 'muted small-text'));
        qrGrid.appendChild(card);
      });
      qrNote.textContent = r.data.local_only
        ? 'Warning: these codes point to ' + r.data.base + ', which a phone cannot open. ' +
          'Set the address of this computer in Settings first.'
        : 'These codes open: ' + r.data.base;
    }

    qrBox.append(
      el('h2', 'QR codes'),
      el('p', 'One QR code for each active table. Print them and stick one on each table.', 'muted'),
      button('Show QR codes', 'primary', showQr),
      button('Print', 'danger', function () { window.print(); }),
      qrNote
    );
    content.appendChild(qrBox);
    content.appendChild(qrGrid);

    // ----- the table list -----
    const t = makeTable(['Table', 'Seats', 'Free now', 'Active', '']);
    t.wrap.classList.add('no-print');
    reply.data.forEach(function (table) {
      const seats = field('number', table.capacity);
      seats.min = '1';
      const active = checkbox(table.is_active);
      const actions = el('div', null, 'row');
      actions.append(
        button('Save', 'primary small', function () {
          act('PATCH', '/admin/tables/' + table.id + '/', {
            capacity: Number(seats.value), is_active: active.checked
          }, 'Table saved.', drawTables);
        }),
        button('Delete', 'danger small', function () {
          if (window.confirm('Delete table ' + table.number + '? A table with old orders can only be switched off.')) {
            act('DELETE', '/admin/tables/' + table.id + '/', undefined, 'Table deleted.', drawTables);
          }
        })
      );
      addRow(t.table, [table.number, seats, table.free_seats, active, actions]);
    });
    content.appendChild(t.wrap);
  }

  // ---------- Staff ----------
  const ROLES = [
    { value: 'admin', label: 'Admin' }, { value: 'chef', label: 'Chef' },
    { value: 'waiter', label: 'Waiter' }, { value: 'cashier', label: 'Cashier' },
    { value: 'gate', label: 'Gate staff' }
  ];

  async function drawStaff() {
    const reply = await STAFF.call('GET', '/admin/staff/');
    if (reply.status !== 200) {
      say(notice, 'The staff list could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Staff'));

    const form = el('div', null, 'card');
    const username = field('text', '', 'Username');
    const fullName = field('text', '', 'Full name');
    const phone = field('text', '', 'Phone');
    const password = field('password', '', 'At least 8 characters');
    password.autocomplete = 'new-password';
    const role = select(ROLES, 'waiter');
    form.append(
      labelled('Username', username), labelled('Full name', fullName), labelled('Phone', phone),
      labelled('Role', role), labelled('Password', password),
      button('Add staff', 'primary', function () {
        act('POST', '/admin/staff/', {
          username: username.value.trim(), full_name: fullName.value.trim(),
          phone: phone.value.trim(), role: role.value, password: password.value
        }, 'Staff added.', drawStaff);
      })
    );
    content.appendChild(form);

    const t = makeTable(['Username', 'Name', 'Role', 'Free', 'Active', '']);
    reply.data.forEach(function (person) {
      const roleBox = select(ROLES, person.role);
      const free = checkbox(person.is_available);
      const active = checkbox(person.is_active);
      const actions = el('div', null, 'row');
      const newPass = field('password', '', 'New password');
      newPass.autocomplete = 'new-password';
      actions.append(
        button('Save', 'primary small', function () {
          act('PATCH', '/admin/staff/' + person.id + '/', {
            role: roleBox.value, is_available: free.checked, is_active: active.checked
          }, 'Staff saved.', drawStaff);
        }),
        newPass,
        button('Set password', 'danger small', async function () {
          const done = await act('POST', '/admin/staff/' + person.id + '/reset-password/',
            { password: newPass.value }, 'Password changed for ' + person.username + '.');
          newPass.value = '';
          if (done.status !== 200) {
            return;
          }
        })
      );
      addRow(t.table, [person.username, person.full_name, roleBox, free, active, actions]);
    });
    content.appendChild(t.wrap);
    content.appendChild(el('p', 'A person is switched off, never deleted, so old orders keep their history.', 'muted'));
  }

  // ---------- Settings ----------
    async function drawSettings() {
    const ring = await STAFF.call('GET', '/admin/settings/');
    const bill = await STAFF.call('GET', '/admin/billing-settings/');
    if (ring.status !== 200 || bill.status !== 200) {
      say(notice, 'The settings could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Settings'));

    content.appendChild(el('h2', 'Kitchen bell'));
    const ringForm = el('div', null, 'card');
    const delay = field('number', ring.data.ring_delay_minutes);
    delay.min = '1';
    const cooldown = field('number', ring.data.ring_cooldown_minutes);
    cooldown.min = '1';
    ringForm.append(
      labelled('Minutes before a customer may ring the kitchen', delay),
      labelled('Minutes to wait between two rings', cooldown),
      button('Save bell settings', 'primary', function () {
        act('PATCH', '/admin/settings/', {
          ring_delay_minutes: Number(delay.value), ring_cooldown_minutes: Number(cooldown.value)
        }, 'Bell settings saved.', drawSettings);
      })
    );
    content.appendChild(ringForm);

    content.appendChild(el('h2', 'Bill'));
    const billForm = el('div', null, 'card');
    const tax = field('number', bill.data.tax_percent);
    tax.step = '0.01';
    tax.min = '0';
    tax.max = '100';
    const discount = field('number', bill.data.discount_percent);
    discount.step = '0.01';
    discount.min = '0';
    discount.max = '100';
    billForm.append(
      labelled('Tax percent', tax),
      labelled('Discount percent for every bill', discount),
      button('Save bill settings', 'primary', function () {
        act('PATCH', '/admin/billing-settings/', {
          tax_percent: tax.value, discount_percent: discount.value
        }, 'Bill settings saved.', drawSettings);
      })
    );
    content.appendChild(billForm);
        content.appendChild(el('h2', 'Address for table QR codes'));
    const addressForm = el('div', null, 'card');
    const address = field('text', ring.data.public_url || '', 'http://192.168.1.5:8000');
    addressForm.append(
      labelled('Address customers open (no slash at the end)', address),
      el('p', 'Leave it empty to use this computer\'s own address. A phone cannot open 127.0.0.1, ' +
        'so type the address of this computer on your Wi-Fi.', 'muted'),
      button('Save address', 'primary', function () {
        act('PATCH', '/admin/settings/', { public_url: address.value.trim() }, 'Address saved.', drawSettings);
      })
    );
    content.appendChild(addressForm);
  }

  // ---------- Orders and groups (read only) ----------
  async function drawOrders() {
    const orders = await STAFF.call('GET', '/admin/orders/?limit=50');
    const groups = await STAFF.call('GET', '/admin/groups/?limit=50');
    if (orders.status !== 200 || groups.status !== 200) {
      say(notice, 'The orders could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Orders'));
    content.appendChild(el('p', 'The newest 50. This page only shows. The chef and the waiter change the status.', 'muted'));

    const t = makeTable(['Order', 'Table', 'Status', 'Waiter', 'Food', 'Total', 'Placed']);
    orders.data.forEach(function (o) {
      const food = o.items.map(function (i) { return i.quantity + ' x ' + i.name; }).join(', ');
      addRow(t.table, [o.id, o.table, o.status, o.waiter || '', food, money(o.total), when(o.created_at)]);
    });
    content.appendChild(t.wrap);

    content.appendChild(el('h2', 'Groups'));
    const g = makeTable(['Group', 'Table', 'Persons', 'Status', 'Orders', 'Created']);
    groups.data.forEach(function (x) {
      addRow(g.table, [x.id, x.table, x.persons, x.status, x.orders, when(x.created_at)]);
    });
    content.appendChild(g.wrap);
  }

  // ---------- Audit log ----------
  async function drawAudit() {
    const reply = await STAFF.call('GET', '/admin/audit/?limit=100');
    if (reply.status !== 200) {
      say(notice, 'The log could not be loaded.');
      return;
    }
    content.replaceChildren();
    content.appendChild(el('h1', 'Audit log'));
    content.appendChild(el('p', 'The newest 100 actions. Nobody can change this list.', 'muted'));
    const t = makeTable(['When', 'Who', 'Action', 'Target', 'Detail']);
    reply.data.forEach(function (r) {
      addRow(t.table, [when(r.when), r.who, r.action, r.target, r.detail]);
    });
    content.appendChild(t.wrap);
  }

  const PAGES = {
    home: drawHome, menu: drawMenu, tables: drawTables, staff: drawStaff,
    settings: drawSettings, orders: drawOrders, audit: drawAudit
  };

  (PAGES[section] || drawHome)();
})();