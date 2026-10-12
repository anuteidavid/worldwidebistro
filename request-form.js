const requestForm = document.querySelector('#request-form');
const feedback = document.querySelector('#form-feedback');

requestForm.addEventListener('submit', async event => {
  event.preventDefault();
  feedback.textContent = '';
  const fields = new FormData(requestForm);
  const payload = Object.fromEntries(fields.entries());

  if (!payload.email.trim() && !payload.phone.trim()) {
    feedback.textContent = 'Adaugă un număr de telefon sau o adresă de e-mail ca să te putem contacta.';
    requestForm.elements.phone.focus();
    return;
  }

  const button = requestForm.querySelector('button[type="submit"]');
  button.disabled = true;
  button.dataset.label = button.innerHTML;
  button.textContent = 'Se trimite…';
  feedback.textContent = 'Trimitem solicitarea…';

  try {
    const response = await fetch('/api/requests', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Solicitarea nu a putut fi trimisă.');
    feedback.textContent = result.message || 'Solicitarea a fost înregistrată.';
    requestForm.reset();
  } catch (error) {
    feedback.textContent = error instanceof TypeError
      ? 'Formularul are nevoie de serverul site-ului. Deschide pagina la adresa locală indicată în instrucțiunile de pornire.'
      : error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = button.dataset.label;
    delete button.dataset.label;
  }
});
