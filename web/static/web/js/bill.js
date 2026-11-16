(function () {
  const app = document.getElementById('app');
  const table = Number(app.dataset.table);
  const PAID_KEY = 'rms_paid_' + table;      // kept after paying, so the receipt can still be shown
  const token = localStorage.getItem('rms_group_' + table) || localStorage.getItem(PAID_KEY);

  const stateEl = document.getElementById('state');
  const notice = document.getElementById('notice');
  const billBox = document.getElementById('bill');
  const payBox = document.getElementById('pay-box');
  const cashBox = document.getElementById('cash-box');
  const receiptBox = document.getElementById('receipt-box');
  const subtotalEl = document.getElementById('subtotal');
  const discountEl = document.getElementById('discount');
  const discountRow = document.getElementById('discount-row');
  const taxEl = document.getElementById('tax');
  const totalEl = document.getElementById('total');
  const infoEl = document.getElementById('info');
  const imageEl = document.getElementById('receipt-image');
  const codeEl = document.getElementById('receipt-code');

  document.getElementById('back').href = '/table/' + table + '/';

  let receiptShown = false;
  let busy = false;

  async function showReceipt() {
    if (receiptShown) {
      return;
    }
    const reply = await api('GET', '/bill/receipt/?token=' + encodeURIComponent(token));
    if (reply.status !== 200) {
      return;
    }
    receiptShown = true;
    imageEl.src = reply.data.image;          // a picture made by our own server
    codeEl.textContent = reply.data.code;
  }

    function hideAll() {
    billBox.hidden = true;
    payBox.hidden = true;
    cashBox.hidden = true;
    receiptBox.hidden = true;
  }

  function draw(d) {
    const paid = d.state === 'paid';
    const cash = d.state === 'cash_requested';
    const unpaid = d.state === 'unpaid';

    if (!paid && !cash && !unpaid) {
      if (d.group_status === 'left') {
        hideAll();
        say(stateEl, 'This visit was closed. Nothing is owed.');
        return;
      }
      if (d.food_waiting) {
        hideAll();
        say(stateEl, 'Your bill will appear when all your food is served.');
        return;
      }
      if (Number(d.total) === 0) {
        hideAll();
        say(stateEl, 'You have not ordered anything yet.');
        return;
      }
    }

    stateEl.hidden = true;
    billBox.hidden = false;
    subtotalEl.textContent = money(d.subtotal);
    discountEl.textContent = '- ' + money(d.discount);
    discountRow.hidden = Number(d.discount) === 0;
    taxEl.textContent = money(d.tax);
    totalEl.textContent = money(d.total);

    payBox.hidden = paid || cash || unpaid || !d.can_pay;
    cashBox.hidden = !cash;
    receiptBox.hidden = !paid;

    if (paid) {
      localStorage.setItem(PAID_KEY, token);
      infoEl.textContent = '';
      showReceipt();
    } else if (unpaid) {
      infoEl.textContent = 'This visit was closed before you paid. Please pay at the cashier, then show your receipt at the exit.';
    } else {
      infoEl.textContent = '';
    }
  }
  
  async function refresh() {
    if (!token) {
      say(stateEl, 'You have no seats at this table yet. Choose your seats first.');
      return;
    }
    const reply = await api('GET', '/bill/?token=' + encodeURIComponent(token));
    if (reply.status !== 200) {
      billBox.hidden = true;
      say(stateEl, 'We could not find your seats. Please choose them again.');
      return;
    }
    draw(reply.data);
  }

  async function act(path, okText, confirmText) {
    if (confirmText && !window.confirm(confirmText)) {
      return;
    }
    if (busy) {
      return;
    }
    busy = true;
    const reply = await api('POST', path, { token: token });
    busy = false;
    if (reply.status === 200) {
      say(notice, okText);
    } else {
      say(notice, (reply.data && reply.data.message) || 'Something went wrong. Please try again.');
    }
    refresh();
  }

  document.getElementById('pay-online').addEventListener('click', function () {
    act('/bill/pay-online/', 'Payment received. Thank you!',
      'Pay ' + totalEl.textContent + ' online? (practice payment)');
  });

  document.getElementById('pay-cash').addEventListener('click', function () {
    act('/bill/ask-cash/', 'The cashier has been told.');
  });

  document.getElementById('cash-cancel').addEventListener('click', function () {
    act('/bill/withdraw-cash/', 'Cash request cancelled.');
  });

  refresh();
    const timer = setInterval(function () {
    if (receiptShown) {
      clearInterval(timer);       // the bill is paid and the receipt is on screen: no need to ask again
      return;
    }
    refresh();
  }, 4000);
})();