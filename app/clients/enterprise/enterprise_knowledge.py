"""Retrieve only published, explicitly registered Dify documents for an employee."""
import hashlib
import json
import re

import httpx

from app.config import settings
from app.core.enterprise.enterprise_authorization import error

_UUID = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
_REFERENCE = re.compile(rf'dify://datasets/({_UUID})/documents/({_UUID})')


def dify_reference(value):
    match = _REFERENCE.fullmatch(value or '')
    return tuple(part.lower() for part in match.groups()) if match else None


class DifyKnowledgeClient:
    def __init__(self, transport=None):
        self.transport = transport

    def _request(self, method, path, **kwargs):
        key = settings.ENTERPRISE_DIFY_DATASET_API_KEY.get_secret_value()
        if not key:
            error(503, '请配置企业知识库服务 API Key；工作流应用 Key 不能用于知识库检索')
        base = settings.ENTERPRISE_DIFY_DATASET_API_BASE or settings.ENTERPRISE_DIFY_API_BASE or settings.DIFY_API_BASE
        try:
            with httpx.Client(timeout=httpx.Timeout(30, connect=5), transport=self.transport, trust_env=False, follow_redirects=False) as client:
                response = client.request(method, base.rstrip('/') + path, headers={'Authorization': 'Bearer ' + key}, **kwargs)
                response.raise_for_status()
                result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Invalid knowledge response')
            return result
        except (httpx.HTTPError, ValueError, TypeError):
            error(503, 'Dify 知识库检索不可用，请检查知识库服务 Key、文档状态和连接配置')

    def document(self, reference):
        dataset, document = reference
        row = self._request('GET', f'/datasets/{dataset}/documents/{document}')
        if (row.get('id') != document or row.get('enabled') is not True or row.get('archived') is True
                or row.get('indexing_status') != 'completed'):
            error(409, 'Dify 来源文档已停用、归档或尚未完成索引，请核实后重试')
        # Ignore usage statistics, which change on every retrieval.
        fields = {key: row.get(key) for key in ('id', 'name', 'updated_at', 'completed_at', 'word_count', 'tokens', 'indexing_status', 'enabled', 'archived')}
        fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return row, fingerprint

    def retrieve(self, question, rows):
        candidates, snapshots = [], {}
        groups = {}
        for row in rows:
            reference = dify_reference(row.get('source_reference'))
            if reference:
                groups.setdefault(reference[0], []).append((reference, row))
        for dataset, entries in groups.items():
            allowed = {}
            for reference, row in entries:
                document, fingerprint = self.document(reference)
                allowed[reference[1]] = (row, document)
                snapshots[reference] = fingerprint
            result = self._request('POST', f'/datasets/{dataset}/retrieve', json={
                'query': question[:250],
                'retrieval_model': {'search_method': 'semantic_search', 'reranking_enable': False,
                                    'top_k': 10, 'score_threshold_enabled': False},
            })
            records = result.get('records')
            if not isinstance(records, list):
                error(503, 'Dify 知识检索返回格式无效')
            seen, chunks, segment_ids = set(), {}, {}
            for record in records:
                segment = record.get('segment') if isinstance(record, dict) else None
                if not isinstance(segment, dict):
                    continue
                document_id = segment.get('document_id')
                segment_id = segment.get('id')
                content = segment.get('content')
                if (not isinstance(document_id,str) or document_id not in allowed or not isinstance(segment_id, str) or not segment_id
                        or not isinstance(content, str) or not content.strip()
                        or segment.get('status') != 'completed' or segment.get('enabled') is not True):
                    continue
                if segment_id in seen:
                    continue
                seen.add(segment_id)
                chunks.setdefault(document_id, []).append(content[:12000])
                segment_ids.setdefault(document_id, []).append(segment_id)
            for document_id, texts in chunks.items():
                row, document = allowed[document_id]
                candidates.append({'id': row['knowledge_id'], 'version': row['version_no'], 'title': row['title'],
                    'content': '\n\n'.join(texts)[:12000], 'knowledge_id': row['knowledge_id'],
                    'source_reference': row['source_reference'], 'document_name': document.get('name') or row['title'],
                    'dataset_id': dataset, 'document_id': document_id, 'segment_ids': segment_ids[document_id]})
        return candidates[:10], snapshots

    def recheck(self, snapshots):
        for reference, fingerprint in snapshots.items():
            if self.document(reference)[1] != fingerprint:
                error(409, 'Dify 来源文档已更新，请重新查询以获取最新答案')
