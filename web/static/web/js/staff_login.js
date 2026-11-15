(function () {
  const form = document.getElementById('login');
  const message = document.getElementById('message');
  const submit = document.getElementById('submit');

  const me = STAFF.read();
  if (me) {
    const home = STAFF.homeFor(me.role);
    if (home) {
      window.location.href = home;
      return;
    }
    STAFF.forget();
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    say(message, '');
    submit.disabled = true;
    const reply = await STAFF.login(
      document.getElementById('username').value.trim(),
      document.getElementById('password').value
    );
    submit.disabled = false;

    if (reply.status === 200) {
      const home = STAFF.homeFor(reply.data.role);
      if (home) {
        window.location.href = home;
        return;
      }
      STAFF.forget();
      say(message, 'There is no page for the role "' + reply.data.role + '" yet.');
    } else if (reply.status === 429) {
      const minutes = Math.ceil((reply.data.wait_seconds || 900) / 60);
      say(message, 'Too many wrong tries. Please wait about ' + minutes + ' minute(s).');
    } else if (reply.status === 401) {
      say(message, 'Wrong username or password.');
    } else {
      say(message, 'Something went wrong. Please try again.');
    }
    document.getElementById('password').value = '';
  });
})();