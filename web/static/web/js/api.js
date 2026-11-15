const API = '/api';

async function api(method, path, body) {
  const options = { method: method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const reply = await fetch(API + path, options);
  let data = null;
  try {
    data = await reply.json();
  } catch (error) {
    data = null;
  }
  return { status: reply.status, data: data };
}

// Make a new element. The text is added as plain text, so it can never run as code.
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) {
    node.textContent = text;
  }
  if (className) {
    node.className = className;
  }
  return node;
}

// Show a message in a box, or hide the box when the text is empty.
function say(node, text) {
  node.textContent = text || '';
  node.hidden = !text;
}

function money(value) {
  return 'Rs ' + Number(value).toFixed(2);
}