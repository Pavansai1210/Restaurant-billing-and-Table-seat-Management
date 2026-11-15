document.getElementById('go').addEventListener('submit', function (event) {
  event.preventDefault();
  const number = Number(document.getElementById('number').value);
  if (number > 0) {
    window.location.href = '/table/' + number + '/';
  }
});