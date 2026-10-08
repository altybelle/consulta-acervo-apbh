const state = { page: 1, total: 0, limit: 20 };
const $ = (selector) => document.querySelector(selector);
const form = $('#search-form');
const results = $('#results');
const pagination = $('#pagination');
const dialog = $('#record-dialog');
const formatter = new Intl.NumberFormat('pt-BR');

const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

async function loadStats() {
  const response = await fetch('/api/stats');
  if (!response.ok) throw new Error('Não foi possível carregar as estatísticas.');
  const stats = await response.json();
  $('#collection-status').textContent = `${formatter.format(stats.total)} registros · ${stats.year_min}–${stats.year_max}`;
  const select = $('#collection');
  stats.collections.forEach(item => {
    const option = document.createElement('option');
    option.value = item.collection;
    option.textContent = `${item.collection} (${formatter.format(item.count)})`;
    select.append(option);
  });
}

function params() {
  const values = new URLSearchParams(new FormData(form));
  [...values.entries()].forEach(([key, value]) => { if (!value.trim()) values.delete(key); });
  values.set('page', state.page);
  return values;
}

function resultCard(item) {
  const date = item.date_text || (item.year ? String(item.year) : 'Data não informada');
  const identity = item.identifier ? `Nº ${item.identifier}` : `Linha ${item.source_row}`;
  const extra = [date, item.management, item.support, item.genre].filter(Boolean).join(' · ');
  return `<article class="result-card">
    <div class="result-id">${escapeHtml(identity)}</div>
    <div>
      <h3>${escapeHtml(item.title || 'Registro sem título')}</h3>
      ${item.description && item.description !== item.title ? `<p class="description">${escapeHtml(item.description)}</p>` : ''}
      <p class="meta">${escapeHtml(item.collection)}${extra ? ` · ${escapeHtml(extra)}` : ''}</p>
    </div>
    <button class="open-record" type="button" data-id="${item.id}">Ver ficha</button>
  </article>`;
}

async function runSearch({ updateHistory = true } = {}) {
  results.setAttribute('aria-busy', 'true');
  results.innerHTML = '<p class="empty">Consultando o inventário…</p>';
  pagination.innerHTML = '';
  try {
    const query = params();
    const response = await fetch(`/api/search?${query}`);
    if (!response.ok) throw new Error('A pesquisa não pôde ser concluída.');
    const data = await response.json();
    Object.assign(state, { total: data.total, page: data.page, limit: data.limit });
    const hasFilters = [...new FormData(form).values()].some(value => value.trim());
    $('#results-heading').textContent = hasFilters ? 'Registros encontrados' : 'Visão geral do inventário';
    $('#result-count').textContent = `${formatter.format(data.total)} ${data.total === 1 ? 'registro' : 'registros'}`;
    results.innerHTML = data.items.length ? data.items.map(resultCard).join('') : '<p class="empty">Nenhum registro corresponde aos termos e filtros informados.</p>';
    renderPagination();
    if (updateHistory) history.replaceState(null, '', `${location.pathname}?${query}`);
  } catch (error) {
    results.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    $('#result-count').textContent = '';
  } finally {
    results.setAttribute('aria-busy', 'false');
  }
}

function renderPagination() {
  const pages = Math.ceil(state.total / state.limit);
  if (pages <= 1) return;
  const candidates = new Set([1, pages, state.page - 1, state.page, state.page + 1]);
  const visible = [...candidates].filter(page => page > 0 && page <= pages).sort((a, b) => a - b);
  const button = (label, page, disabled = false, current = false) => `<button type="button" data-page="${page}" ${disabled ? 'disabled' : ''} ${current ? 'aria-current="page"' : ''}>${label}</button>`;
  let html = button('‹', state.page - 1, state.page === 1);
  visible.forEach((page, index) => {
    if (index && page - visible[index - 1] > 1) html += '<span aria-hidden="true">…</span>';
    html += button(page, page, false, page === state.page);
  });
  html += button('›', state.page + 1, state.page === pages);
  pagination.innerHTML = html;
}

async function openRecord(id) {
  const response = await fetch(`/api/records/${id}`);
  if (!response.ok) return;
  const item = await response.json();
  $('#dialog-collection').textContent = item.collection;
  $('#dialog-title').textContent = item.title || 'Registro sem título';
  const fields = Object.entries(item.fields).filter(([, value]) => value);
  fields.push(['Arquivo de origem', `${item.source_file}, linha ${item.source_row}`]);
  $('#dialog-content').innerHTML = `<dl>${fields.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}</dl>`;
  dialog.showModal();
}

form.addEventListener('submit', event => { event.preventDefault(); state.page = 1; runSearch(); });
$('#collection').addEventListener('change', () => { state.page = 1; runSearch(); });
$('#clear-button').addEventListener('click', () => { form.reset(); state.page = 1; runSearch(); $('#query').focus(); });
results.addEventListener('click', event => { const button = event.target.closest('[data-id]'); if (button) openRecord(button.dataset.id); });
pagination.addEventListener('click', event => { const button = event.target.closest('[data-page]'); if (!button || button.disabled) return; state.page = Number(button.dataset.page); runSearch(); window.scrollTo({ top: $('.results-section').offsetTop - 20, behavior: 'smooth' }); });
$('#close-dialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

async function initialize() {
  const initial = new URLSearchParams(location.search);
  state.page = Math.max(1, Number(initial.get('page')) || 1);
  try {
    await loadStats();
    ['q', 'collection', 'year_from', 'year_to'].forEach(name => { if (initial.has(name)) form.elements[name].value = initial.get(name); });
    await runSearch({ updateHistory: false });
  }
  catch (error) { results.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`; }
}
initialize();
