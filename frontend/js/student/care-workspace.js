import {api, esc, createList, dateText} from './ui.js';

export async function render(root) {
  root.innerHTML = `<details class="section-card live-section" open><summary>提交心情反馈</summary><div class="live-body"><form id="care-feedback-form" class="care-feedback-form"><div class="form-field"><label for="care-feedback-content">想说的话</label><textarea id="care-feedback-content" name="chat_content" rows="5" maxlength="10000" required placeholder="最近有哪些事情让你开心、困扰，或希望得到支持？"></textarea></div><p class="muted">你的反馈会保存在本人记录中。</p><div class="form-actions"><button class="button" type="submit">提交反馈</button></div><p role="status" data-care-status></p></form></div></details>
  <details class="section-card live-section" open><summary>查看反馈与回复</summary><div class="live-body"><p class="muted">这里展示从本功能提交的反馈和公开关怀建议。</p><button type="button" class="button secondary" data-care-refresh>刷新反馈</button><div data-care-history></div></div></details>
  <details class="section-card live-section" open><summary>安慰与建议</summary><div class="live-body"><div data-care-support role="status"><h3>给自己一点空间</h3><p>先放慢节奏，给自己一点休息的时间。也可以和信任的人说说，或与助手继续聊聊。</p></div><a class="button secondary" href="/student/chat.html?prompt=${encodeURIComponent('最近我有些压力，想聊聊。')}" data-care-chat>与助手聊聊</a><p class="muted">这里提供通用关怀建议；老师的内部跟进记录不会在此展示。</p></div></details>`;
  const form = root.querySelector('#care-feedback-form');
  const message = form.querySelector('[data-care-status]');
  const support = root.querySelector('[data-care-support]');
  function showSupport(row) {
    support.innerHTML = '<h3>给你的关怀建议</h3>';
    const text = document.createElement('p'); text.textContent = row.reply || '本次反馈结果待核实，请稍后刷新查看。'; support.append(text);
    support.closest('details').open = true;
  }
  const history = createList(root.querySelector('[data-care-history]'), {
    fetchPage: (limit, offset) => api('student/mental/feedback?limit=' + limit + '&offset=' + offset),
    emptyTitle: '还没有心情反馈', emptyText: '提交后，你的反馈与公开回复会出现在这里。', iconName: 'heart',
    render: rows => rows.map(row => `<article class="care-feedback-record"><div class="care-feedback-meta"><time>${esc(dateText(row.created_at))}</time><span>${row.status === 'completed' ? '已有回复' : '结果待核实'}</span></div><h3>我的反馈</h3><p class="care-feedback-text">${esc(row.content)}</p><h3>关怀回复</h3><p class="care-feedback-text">${esc(row.reply || '反馈已记录，回复结果待核实。请稍后刷新查看。')}</p><button type="button" class="button secondary" data-care-view="${esc(row.id)}">查看建议</button></article>`).join(''),
    afterRender: (body, rows) => body.querySelectorAll('[data-care-view]').forEach(button => {
      button.onclick = () => { const row = rows.find(item => String(item.id) === button.dataset.careView); if (row) showSupport(row); };
    }),
  });
  root.querySelector('[data-care-refresh]').onclick = () => history.load(true);
  const submit = form.querySelector('[type=submit]');
  form.onsubmit = async event => {
    event.preventDefault(); if (submit.disabled || !form.reportValidity()) return;
    const text = form.elements.chat_content.value.trim();
    if (!text) { message.textContent = '请填写心情反馈。'; return; }
    submit.disabled = true; message.textContent = '正在提交，请稍候……';
    try { const row = await api('student/mental/feedback', {method: 'POST', body: {chat_content: text}}); form.reset(); showSupport(row); message.textContent = '反馈已保存，可以在下方查看。'; }
    catch (error) { message.textContent = error.message; }
    finally { submit.disabled = false; await history.load(true); }
  };
  await history.load();
}
