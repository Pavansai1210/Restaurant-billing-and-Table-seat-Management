(function () {
  const me = STAFF.require('gate', 'admin');
  if (!me) {
    return;
  }

  const form = document.getElementById('check');
  const input = document.getElementById('code');
  const submit = document.getElementById('submit');
  const resultEl = document.getElementById('result');
  const historyEl = document.getElementById('history');

  document.getElementById('who').textContent = 'Logged in as ' + me.username + ' (' + me.role + ')';
  document.getElementById('logout').addEventListener('click', STAFF.logout);
  if (me.role === 'admin') {
    document.getElementById('to-panel').hidden = false;
  }

  const WORDS = {
    ok: 'PAID. LET THEM GO',
    used: 'ALREADY USED. DO NOT LET THEM GO',
    unknown: 'NOT VALID. SEND THEM TO THE CASHIER'
  };
  const recent = [];

  function drawResult(data) {
    resultEl.hidden = false;
    resultEl.className = 'result ' + (data.result === 'ok' ? 'ok' : 'bad');
    resultEl.textContent = (WORDS[data.result] || data.result) +
      (data.table ? ' (table ' + data.table + ')' : '');
  }

  function drawHistory(code, data) {
    recent.unshift({
      time: new Date().toLocaleTimeString(),
      code: code.slice(0, 6) + '...',
      result: data.result
    });
    recent.length = Math.min(recent.length, 10);
    historyEl.replaceChildren();
    recent.forEach(function (r) {
      historyEl.appendChild(el('li', r.time + ' - ' + r.code + ' - ' + r.result));
    });
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const code = input.value.trim();
    if (!code) {
      return;
    }
    submit.disabled = true;
    const reply = await STAFF.call('POST', '/gate/check/', { code: code });
    submit.disabled = false;

    if (reply.status === 200) {
      drawResult(reply.data);
      drawHistory(code, reply.data);
    } else {
      resultEl.hidden = false;
      resultEl.className = 'result bad';
      resultEl.textContent = 'Could not check. Please try again.';
    }
    input.value = '';
    input.focus();
  });

  input.focus();
})();