/* Static layout preview: local-only interactions. Never calls business APIs. */
(() => {
  'use strict';
  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => [...root.querySelectorAll(q)];
  const toast = (message) => {
    const stack = $('.toast-stack');
    if (!stack) return;
    const node = document.createElement('div'); node.className = 'toast'; node.textContent = message;
    stack.append(node); setTimeout(() => node.remove(), 4300);
  };
  let previousFocus;
  const closeModal = () => {
    const overlay = $('#preview-modal');
    if (!overlay || overlay.hidden) return;
    overlay.hidden = true; document.body.style.overflow = ''; previousFocus?.focus();
  };
  const openModal = (title, kind) => {
    const overlay = $('#preview-modal'); if (!overlay) return;
    previousFocus = document.activeElement;
    $('#modal-title').textContent = title;
    const body = $('#modal-body'); body.replaceChildren();
    const description = document.createElement('p'); description.className = 'section-caption';
    description.textContent = '填写以下内容，预览表单与确认流程。示例操作不会提交到业务系统。'; body.append(description);
    const form = document.createElement('form'); form.className = 'preview-form'; form.dataset.message = '已保存本次布局演示内容，未提交业务数据。';
    const groups = kind === 'assign' ? [['负责人', 'select'], ['分派原因', 'textarea']] :
      kind === 'signup' ? [['报名姓名', 'text'], ['联系电话', 'tel'], ['联系邮箱', 'email']] :
      kind === 'review' ? [['审批结果', 'select'], ['审批意见', 'textarea']] :
      kind === 'reminder' ? [['提醒事项', 'text'], ['提前提醒时间', 'select']] :
      kind === 'confirm' ? [['确认事项', 'text'], ['操作说明', 'textarea']] :
      kind === 'customer' ? [['客户姓名', 'text'], ['联系电话', 'tel'], ['意向国家', 'select'], ['备注', 'textarea']] :
      kind === 'account' ? [['账号名称', 'text'], ['账号身份', 'select'], ['所属部门', 'select']] :
      [['名称', 'text'], ['说明或备注', 'textarea']];
    groups.forEach(([label, type]) => {
      const field = document.createElement('div'); field.className = 'form-field';
      const labelNode = document.createElement('label'); labelNode.textContent = label; const id = `modal-field-${form.children.length}`; labelNode.htmlFor = id;
      const input = document.createElement(type === 'textarea' ? 'textarea' : type === 'select' ? 'select' : 'input');
      input.id = id; input.required = true; input.name = label;
      if (type === 'select') {
        const options = label.includes('审批') ? ['请选择', '同意', '驳回并填写原因'] : label.includes('身份') ? ['请选择', '平台管理员', '员工', '客户', '学生'] : label.includes('提醒') ? ['请选择', '提前1小时', '提前1天', '提前3天'] : label.includes('国家') ? ['请选择', '英国', '美国', '澳大利亚', '新加坡'] : label.includes('部门') ? ['请选择', '留学咨询部', '教务服务部', '综合管理部'] : ['请选择', '陈老师', '林顾问', '王主管'];
        options.forEach((text, i) => input.add(new Option(text, i ? text : '')));
      } else if (type !== 'textarea') input.type = type;
      input.placeholder = `请输入${label}`; field.append(labelNode, input); form.append(field);
    });
    const actions = document.createElement('div'); actions.className = 'form-actions';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'button secondary'; cancel.dataset.closeModal = ''; cancel.textContent = '取消';
    const submit = document.createElement('button'); submit.type = 'submit'; submit.className = 'button'; submit.textContent = kind === 'confirm' ? '确认办理' : '确认保存';
    actions.append(cancel, submit); form.append(actions); body.append(form);
    overlay.hidden = false; document.body.style.overflow = 'hidden'; $('input,select,textarea,button', body)?.focus();
  };
  document.addEventListener('click', event => {
    const menu = event.target.closest('[data-menu]'); if (menu) document.body.classList.toggle('rail-open');
    if (event.target.closest('.mobile-scrim')) document.body.classList.remove('rail-open');
    const close = event.target.closest('[data-close-modal]'); if (close) closeModal();
    if (event.target.id === 'preview-modal') closeModal();
    const modal = event.target.closest('[data-modal]'); if (modal) openModal(modal.dataset.modal, modal.dataset.kind);
    const note = event.target.closest('[data-toast]'); if (note) toast(note.dataset.toast);
    if (event.target.closest('[data-print]')) window.print();
    const tab = event.target.closest('[data-tab]');
    if (tab) {
      const group = tab.closest('[data-tabs]');
      if (group) {
        $$('[data-tab]', group).forEach(t => {t.classList.toggle('active', t === tab); t.setAttribute('aria-selected', String(t === tab));});
        const section = group.parentElement;
        $$('[data-tab-panel]', section).forEach(panel => panel.hidden = panel.dataset.tabPanel !== tab.dataset.tab);
      }
    }
    const chip = event.target.closest('[data-filter-chip]');
    if (chip) { $$('[data-filter-chip]', chip.parentElement).forEach(x => x.classList.toggle('active', x === chip)); toast(`已选择“${chip.textContent.trim()}”分类`); }
    const emotion = event.target.closest('.emotion-choice');
    if (emotion) { $$('.emotion-choice').forEach(x => { x.classList.toggle('selected', x === emotion); x.setAttribute('aria-pressed',String(x===emotion)); }); }
    const read = event.target.closest('[data-read-all]');
    if (read) { $$('.notification.unread').forEach(n => n.classList.remove('unread')); toast('本页示例通知已标记为已读'); }
    const suggestion = event.target.closest('[data-suggest]');
    if (suggestion) { const input = $('[data-chat-input]'); if (input) {input.value = suggestion.dataset.suggest || suggestion.textContent.trim(); input.focus();} }
    const pag = event.target.closest('.pagination .numbers button');
    if (pag) { $$('.pagination .numbers button').forEach(b=>b.classList.toggle('active',b===pag)); toast('当前为页面布局预览，展示同一组示例记录'); }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {closeModal(); document.body.classList.remove('rail-open');}
    const overlay = $('#preview-modal');
    if (event.key === 'Tab' && overlay && !overlay.hidden) {
      const focusable = $$('button,input,textarea,select,a[href]', overlay).filter(x => !x.disabled);
      if (event.shiftKey && document.activeElement === focusable[0]) {event.preventDefault();focusable.at(-1)?.focus();}
      else if (!event.shiftKey && document.activeElement === focusable.at(-1)) {event.preventDefault();focusable[0]?.focus();}
    }
  });
  const filterTables = () => {
    const search = $('[data-table-search]'); const filter = $('[data-table-filter]');
    const term = search?.value.trim().toLowerCase() || ''; const status = filter?.value || '';
    let count = 0;
    $$('tbody tr[data-search-row]').forEach(row => {row.hidden = !row.textContent.toLowerCase().includes(term) || (status && row.dataset.status !== status); if(!row.hidden) count++;});
    const empty = $('[data-no-results]'); if(empty) empty.hidden = count !== 0;
    const number = $('[data-visible-count]'); if(number) number.textContent = count;
  };
  document.addEventListener('input', e => { if(e.target.matches('[data-table-search]')) filterTables(); if(e.target.matches('[data-map-search]')) {const term=e.target.value.trim();$$('.map-link').forEach(n=>n.hidden=!n.textContent.includes(term));} });
  document.addEventListener('change', e => {
    if(e.target.matches('[data-table-filter]')) filterTables();
    if(e.target.matches('[data-select-all]')) $$('.table-check:not([data-select-all])').forEach(n=>n.checked=e.target.checked);
    if(e.target.matches('input[type=file]')) {const info=$('[data-file-info]',e.target.closest('.upload-zone')); if(info) info.textContent=e.target.files.length ? `${e.target.files[0].name} · ${(e.target.files[0].size/1024).toFixed(1)} KB` : '尚未选择文件';}
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if(!form.matches('.preview-form,[data-chat-form],[data-login-preview]')) return;
    event.preventDefault();
    if(form.matches('[data-chat-form]')) {
      const input = $('[data-chat-input]',form); const text=input.value.trim(); if(!text)return;
      const feed=$('[data-chat-feed]');
      const append=(content,user=false)=>{const row=document.createElement('div');row.className=`message${user?' user':''}`;const avatar=document.createElement('div');avatar.className='avatar';avatar.textContent=user?'我':'✦';const bubble=document.createElement('div');bubble.className='bubble';bubble.textContent=content;row.append(avatar,bubble);feed.append(row);feed.scrollTop=feed.scrollHeight;};
      append(text,true);input.value='';
      setTimeout(()=>append('已收到你的问题。这里展示智能对话的页面效果；正式接入后，将根据你的身份与授权资料返回相应内容。你可以继续浏览右侧或侧栏中的服务页面。'),350);
      return;
    }
    if(form.matches('[data-login-preview]')) {toast('正在进入布局预览工作台');setTimeout(()=>location.href='../dashboard/dashboard.html',400);return;}
    const start=form.querySelector('[name=start_time]'), end=form.querySelector('[name=end_time]');
    if(start?.value&&end?.value&&start.value>=end.value){toast('结束时间需要晚于开始时间');end.focus();return;}
    toast(form.dataset.message || '已保存本次页面演示内容，未提交业务数据。');
    if(form.closest('#preview-modal')) closeModal();
  });
  $$('[data-reveal]').forEach(el=>el.classList.add('visible'));
})();
