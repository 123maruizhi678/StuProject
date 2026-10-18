"""No production DB or external API: verify the authorized Dify retrieval boundary."""
from datetime import datetime, timedelta
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from pydantic import SecretStr
from sqlalchemy import insert, update

from app.clients.enterprise.enterprise_knowledge import DifyKnowledgeClient, dify_reference
from app.core.common.response import BusinessException
from app.models.enterprise import knowledge_entry as table
from app.services.enterprise.enterprise_knowledge import KnowledgeService
from tests.enterprise.test_enterprise import EnterpriseTests

DATASET='a43aba50-4af1-4062-bc56-47c6255e5da4'
DOCUMENT='11111111-2222-4333-8444-555555555555'
REFERENCE=f'dify://datasets/{DATASET}/documents/{DOCUMENT}'


class RetrievalTransport:
    def __init__(self):
        self.calls=[]
        self.enabled=True
        self.updated=1
        self.records=[self.segment(DOCUMENT,'s-allowed','进入学生智能助手的请假办理，填写类型、起止时间和原因后提交。')]

    @staticmethod
    def segment(document, identity, text):
        return {'score':0.9,'segment':{'id':identity,'document_id':document,'content':text,'enabled':True,'status':'completed'}}

    def __call__(self, request):
        self.calls.append((request.method,request.url.path))
        if request.method=='GET':
            return httpx.Response(200,json={'id':DOCUMENT,'name':'学生请假申请与审批流程.docx','enabled':self.enabled,'archived':False,'indexing_status':'completed','word_count':2323,'updated_at':self.updated})
        assert request.url.path==f'/v1/datasets/{DATASET}/retrieve'
        assert json.loads(request.content)['query']
        return httpx.Response(200,json={'records':self.records})


class KnowledgeIntegrationTests(unittest.TestCase):
    # Reuse the SQLite fixtures without inheriting unrelated regression tests.
    repository=EnterpriseTests.repository
    tearDown=EnterpriseTests.tearDown
    def register(self, **overrides):
        now=datetime.utcnow()
        values=dict(entry_code='leave-dify',title='学生手续说明',entry_type='document',category_code='internal',employee_id=1,source_reference=REFERENCE,content_text=None,access_department_id=1,version_no=1,row_version=1,status='published',index_status='ready',effective_from=now-timedelta(days=1))
        values.update(overrides)
        identity=self.db.execute(insert(table).values(**values)).inserted_primary_key[0]
        self.db.commit()
        return identity

    def setUp(self):
        EnterpriseTests.setUp(self)
        self.remote=RetrievalTransport()
        self.retriever=DifyKnowledgeClient(httpx.MockTransport(self.remote))
        from app.clients.enterprise import enterprise_knowledge
        config=SimpleNamespace(ENTERPRISE_DIFY_DATASET_API_KEY=SecretStr('mock-dataset-key'),ENTERPRISE_DIFY_DATASET_API_BASE='http://dify.test/v1')
        patcher=patch.object(enterprise_knowledge,'settings',config)
        patcher.start();self.addCleanup(patcher.stop)
        self.model_calls=[]

        def run(scene, payload, user):
            self.model_calls.append((scene,payload,user))
            candidate=payload['candidates'][0]
            if hasattr(self,'during_model'):self.during_model()
            citations=getattr(self,'model_citations',[{'id':candidate['id'],'version':candidate['version']}])
            return {'answer':'进入学生智能助手 → 请假办理，填写类型、起止时间及原因并提交。','citations':citations,'mode':payload['mode']}

        self.model=SimpleNamespace(run=run)

    def ask(self, repo=None):
        return KnowledgeService(repo or self.repo,self.model,self.retriever).ask('怎么请假')

    def test_external_document_without_literal_title_match_answers_with_source(self):
        identity=self.register()
        answer=self.ask()
        self.assertIn('请假办理',answer['answer'])
        self.assertEqual(answer['mode'],'rag')
        self.assertEqual(answer['citations'][0]['id'],identity)
        self.assertEqual(answer['citations'][0]['dataset_id'],DATASET)
        self.assertEqual(answer['citations'][0]['segment_ids'],['s-allowed'])
        self.assertEqual(answer['citations'][0]['document_name'],'学生请假申请与审批流程.docx')
        self.assertEqual(self.model_calls[0][1]['candidates'][0]['id'],identity)

    def test_other_department_draft_expired_or_disabled_never_reaches_dify(self):
        identity=self.register()
        self.assertEqual(self.ask(self.repository(3))['mode'],'no_source')
        for values in ({'status':'draft'},{'status':'disabled'},{'status':'published','expires_at':datetime.utcnow()-timedelta(days=1)}):
            self.db.execute(update(table).where(table.c.knowledge_id==identity).values(**values));self.db.commit()
            self.assertEqual(self.ask()['mode'],'no_source')
        self.assertFalse(self.remote.calls)
        self.assertFalse(self.model_calls)

    def test_unregistered_disabled_and_incomplete_segments_are_excluded(self):
        self.register()
        foreign=RetrievalTransport.segment('unauthorized-document','other','不应传给模型')
        disabled=RetrievalTransport.segment(DOCUMENT,'disabled','不应传给模型');disabled['segment']['enabled']=False
        incomplete=RetrievalTransport.segment(DOCUMENT,'incomplete','不应传给模型');incomplete['segment']['status']='indexing'
        self.remote.records.extend([foreign,disabled,incomplete])
        self.ask()
        self.assertNotIn('不应传给模型',str(self.model_calls))

    def test_no_hits_does_not_call_answer_model(self):
        self.register();self.remote.records=[]
        self.assertEqual(self.ask()['mode'],'no_source')
        self.assertFalse(self.model_calls)

    def test_missing_dataset_key_is_an_error_not_no_source(self):
        self.register()
        from app.clients.enterprise import enterprise_knowledge
        with patch.object(enterprise_knowledge.settings,'ENTERPRISE_DIFY_DATASET_API_KEY',SecretStr('')):
            with self.assertRaises(BusinessException) as failure:self.ask()
        self.assertEqual(failure.exception.code,503)
        self.assertFalse(self.model_calls)

    def test_forged_or_unhashable_citations_are_rejected(self):
        self.register()
        for citations in ([{'id':999999,'version':1}],[{'id':{},'version':1}],[{'id':True,'version':1}],[]):
            self.model_citations=citations
            with self.assertRaises(BusinessException) as failure:self.ask()
            self.assertEqual(failure.exception.code,503)

    def test_mid_request_source_revocation_is_rejected(self):
        identity=self.register()
        self.during_model=lambda:(self.db.execute(update(table).where(table.c.knowledge_id==identity).values(status='disabled')),self.db.commit())
        with self.assertRaises(BusinessException) as failure:self.ask()
        self.assertEqual(failure.exception.code,409)

    def test_mid_request_employee_revocation_is_rejected(self):
        from app.models import common as common
        self.register()
        self.during_model=lambda:(self.db.execute(update(common.employee).where(common.employee.c.employee_id==1).values(status='disabled')),self.db.commit())
        with self.assertRaises(BusinessException) as failure:self.ask()
        self.assertEqual(failure.exception.code,403)

    def test_remote_document_changes_are_rechecked(self):
        self.register()
        self.during_model=lambda:setattr(self.remote,'updated',2)
        with self.assertRaises(BusinessException) as failure:self.ask()
        self.assertEqual(failure.exception.code,409)

    def test_invalid_reference_cannot_be_used_as_arbitrary_url(self):
        self.assertIsNone(dify_reference('http://untrusted.test/secret'))
        with self.assertRaises(BusinessException):KnowledgeService.content({'entry_type':'document','source_reference':'dify://localhost/secret'})
        KnowledgeService.content({'entry_type':'document','source_reference':REFERENCE})


if __name__=='__main__':unittest.main()
