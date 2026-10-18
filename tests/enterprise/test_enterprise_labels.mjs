import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { test } from 'node:test';
import { LABELS } from '../../frontend/js/workspace/pages.js';

test('企业弹窗数据模型的非敏感字段均有中文名称',async()=>{
  const fields=new Set();
  for(const directory of ['common','enterprise','student']){
    const root=new URL(`../../app/models/${directory}/`,import.meta.url);
    for(const file of await readdir(root)){
      if(!file.endsWith('.py'))continue;
      const source=await readFile(new URL(file,root),'utf8');
      for(const match of source.matchAll(/Column\(\s*['"]([^'"]+)['"]/g))fields.add(match[1]);
      for(const match of source.matchAll(/^\s+(\w+):\s*Mapped\[/gm))fields.add(match[1]);
    }
  }
  const visible=[...fields].filter(key=>!/password|ciphertext|lookup_token|secret|request_hash|parameters_hash/.test(key)&&key!=='request_key');
  const missing=visible.filter(key=>!/[\u3400-\u9fff]/.test(LABELS[key]||''));
  assert.deepEqual(missing,[],'新增模型字段时须补齐弹窗中文名称');
});

test('协作表单及嵌套返回结构使用中文字段名',()=>{
  for(const key of ['status_changed_at','last_followup_at','external_updated_at','is_archived','source_timezone',
    'source_updated_at','external_application_id','external_event_id','records','items','rows','tree','kind','unread','citations','needs_clarification']){
    assert.match(LABELS[key],/[\u3400-\u9fff]/,key);
  }
});
