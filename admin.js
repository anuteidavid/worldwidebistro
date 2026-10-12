const loginPanel = document.querySelector('#login-panel');
const dashboard = document.querySelector('#dashboard');
const loginForm = document.querySelector('#login-form');
const loginFeedback = document.querySelector('#login-feedback');
const dashboardFeedback = document.querySelector('#dashboard-feedback');
const requestList = document.querySelector('#request-list');
const requestCount = document.querySelector('#request-count');
const statuses = ['Nouă', 'Contactată', 'Confirmată', 'Închisă'];

function showDashboard(show) {
  loginPanel.hidden = show;
  dashboard.hidden = !show;
}

async function api(path, options={}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'A apărut o eroare.');
  return result;
}

function addText(parent, tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function createRequestCard(item) {
  const card = document.createElement('article');
  card.className = 'request-card';
  const top = document.createElement('div');
  top.className = 'request-card-top';
  const title = document.createElement('div');
  addText(title, 'h2', '', item.full_name);
  addText(title, 'p', 'request-type', item.request_type);
  top.append(title);

  const statusLabel = document.createElement('label');
  statusLabel.className = 'status-control';
  addText(statusLabel, 'span', '', 'Stare');
  const status = document.createElement('select');
  statuses.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    option.selected = value === item.status;
    status.append(option);
  });
  status.addEventListener('change', async () => {
    status.disabled = true;
    try {
      await api(`/api/admin/requests/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({status: status.value}),
      });
      item.status = status.value;
      dashboardFeedback.textContent = 'Starea solicitării a fost actualizată.';
    } catch (error) {
      dashboardFeedback.textContent = error.message;
      status.value = item.status;
    } finally {
      status.disabled = false;
    }
  });
  statusLabel.append(status);
  top.append(statusLabel);
  card.append(top);

  const timestamp = new Date(item.created_at);
  addText(card, 'p', 'request-date', Number.isNaN(timestamp.getTime()) ? item.created_at : timestamp.toLocaleString('ro-RO'));
  const contact = document.createElement('div');
  contact.className = 'request-contact';
  if (item.phone) {
    const phone = document.createElement('a');
    phone.href = `tel:${item.phone.replace(/[^+\d]/g, '')}`;
    phone.textContent = item.phone;
    contact.append(phone);
  }
  if (item.email) {
    const email = document.createElement('a');
    email.href = `mailto:${item.email}`;
    email.textContent = item.email;
    contact.append(email);
  }
  card.append(contact);

  const details = document.createElement('dl');
  details.className = 'request-details';
  const values = [
    ['Data dorită', item.event_date || 'Nespecificată'],
    ['Ora', item.event_time || 'Nespecificată'],
    ['Persoane', item.guests == null ? 'Nespecificat' : String(item.guests)],
    ['Notificare e-mail', item.email_sent ? 'Trimisă' : 'Neconfigurată sau netrimisă'],
  ];
  values.forEach(([label, value]) => {
    addText(details, 'dt', '', label);
    addText(details, 'dd', '', value);
  });
  card.append(details);
  if (item.message) addText(card, 'p', 'request-message', item.message);
  return card;
}

async function loadRequests() {
  dashboardFeedback.textContent = '';
  requestCount.textContent = 'Se încarcă solicitările…';
  try {
    const result = await api('/api/admin/requests');
    showDashboard(true);
    requestCount.textContent = `${result.requests.length} solicitări`;
    requestList.replaceChildren();
    if (!result.requests.length) {
      addText(requestList, 'p', 'empty-state', 'Nu există solicitări noi momentan.');
      return;
    }
    result.requests.forEach(item => requestList.append(createRequestCard(item)));
  } catch (error) {
    if (error.message === 'Autentificare necesară.') {
      showDashboard(false);
      return;
    }
    requestCount.textContent = '';
    dashboardFeedback.textContent = error.message;
  }
}

loginForm.addEventListener('submit', async event => {
  event.preventDefault();
  loginFeedback.textContent = 'Se verifică datele…';
  const button = loginForm.querySelector('button');
  button.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(loginForm).entries());
    await api('/api/admin/login', {method: 'POST', body: JSON.stringify(payload)});
    loginForm.reset();
    await loadRequests();
  } catch (error) {
    loginFeedback.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#refresh-button').addEventListener('click', loadRequests);
document.querySelector('#logout-button').addEventListener('click', async () => {
  try {
    await api('/api/admin/logout', {method: 'POST', body: '{}'});
    showDashboard(false);
    loginFeedback.textContent = 'Te-ai deconectat.';
  } catch (error) {
    dashboardFeedback.textContent = error.message;
  }
});

loadRequests();
