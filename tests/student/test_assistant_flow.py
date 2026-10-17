from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import json
import httpx
import pytest
from sqlalchemy import select, func
from app.clients.student.student_clients import get_dify
from app.schemas.student.student import ChatDecision
from app.models import common as t
from app.models.student.student_conversation import turns, sessions
from app.services.student.student_service import profiles
from app.config import settings
from .test_minimal_units import post


@pytest.fixture
def model(unit):
    class Model:
        calls=0
        callback=None
        response={'intent':'feedback','answer':'请确认','action':'ticket.submit',
                  'parameters':{'content':'课程安排需要调整'},'summary':'需要说明课程安排',
                  'mental':{'emotion_tag':'平稳','emotion_score':80,'risk_level':'low','workflow_run_id':'test-run'}}
        def run(self,*args,**kwargs):
            self.calls+=1
            if self.callback:
                self.callback()
            return ChatDecision.model_validate(self.response),'test-run'
        def mental(self,*args,**kwargs):
            self.calls+=1
            if self.callback:
                self.callback()
            return ChatDecision.model_validate(self.response).mental
    model=Model()
    unit.app.dependency_overrides[get_dify]=lambda:model
    return model


def test_preview_confirm_replay_and_expired_success(unit,model,monkeypatch):
    first=post(unit,'student/chat',{'message':'反馈课程安排'})
    assert first['code']==0,first
    assert post(unit,'student/chat',{'message':'反馈课程安排'})==first
    with unit.sessions() as db:
        assert db.scalar(select(func.count()).select_from(t.service_ticket))==0
        assert db.scalar(select(func.count()).select_from(profiles))==1
    assert model.calls==1
    body={'action_token':first['data']['pending_action']['action_token']}
    result=post(unit,'student/actions/confirm',body,'confirm-0001')
    assert result['code']==0,result
    from app.core.student import student_auth
    original=student_auth.time.time
    monkeypatch.setattr(student_auth.time,'time',lambda:original()+400)
    assert post(unit,'student/actions/confirm',body,'confirm-0001')==result
    assert post(unit,'student/actions/confirm',body,'confirm-0002')==result
    assert model.calls==1
    with unit.sessions() as db:
        assert db.scalar(select(func.count()).select_from(t.service_ticket))==1


def test_conversation_scope_version_and_forged_model(unit,model):
    from app.core.student.student_auth import Principal
    first=post(unit,'student/chat',{'message':'第一条'})['data']
    token=first['conversation_token']
    second=post(unit,'student/chat',{'message':'第二条','conversation_token':token},'message-0002')
    assert second['code']==0,second
    assert post(unit,'student/chat',{'message':'旧会话','conversation_token':token},'message-0003')['code']==409
    unit.state.actor=Principal('student',8,scopes=unit.state.actor.scopes)
    assert post(unit,'student/chat',{'message':'盗用会话','conversation_token':token},'message-0004')['code']==403
    unit.state.actor=Principal('student',7,scopes=unit.state.actor.scopes)
    model.response={**model.response,'parameters':{'content':'反馈','student_id':8}}
    assert post(unit,'student/chat',{'message':'新会话'},'message-0005')['code']==400


def test_duplicate_during_model_call_has_one_execution(unit,model):
    entered,release=Event(),Event()
    def block():
        entered.set()
        assert release.wait(10)
    model.callback=block
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(post,unit,'student/chat',{'message':'并发消息'},'parallel-0001')
        try:
            assert entered.wait(5)
            duplicate=post(unit,'student/chat',{'message':'并发消息'},'parallel-0001')
            assert duplicate['code']==409,duplicate
            assert model.calls==1
        finally:
            release.set()
        assert future.result(timeout=10)['code']==0
    assert post(unit,'student/chat',{'message':'并发消息'},'parallel-0001')['code']==0
    assert model.calls==1


def test_unknown_model_result_never_automatically_retries(unit,model):
    from app.core.common.response import BusinessException
    def fail():
        raise BusinessException('模型结果待核实',503)
    model.callback=fail
    assert post(unit,'student/chat',{'message':'超时'},'timeout-0001')['code']==503
    assert post(unit,'student/chat',{'message':'超时'},'timeout-0001')['code']==409
    assert model.calls==1
    from app.tasks.student.student_tasks import StudentTasks
    assert len(StudentTasks(unit.sessions).pending_model_results())==1


def test_direct_mental_monitor_replays_and_deduplicates(unit,model):
    result=post(unit,'student/mental/monitor',{'chat_content':'测试消息'})
    assert result['code']==0,result
    assert post(unit,'student/mental/monitor',{'chat_content':'测试消息'})==result
    assert model.calls==1
    with unit.sessions() as db:
        assert db.scalar(select(func.count()).select_from(profiles))==1


def test_unique_client_uses_common_transport_and_root_config(monkeypatch):
    from app.clients.student.student_assistant_dify import StudentAssistantDifyClient
    from pydantic import SecretStr
    from app.core.student.student_auth import Principal
    seen=[]
    def upstream(request):
        seen.append(request)
        assert str(request.url)=='http://dify.test/v1/workflows/run'
        assert request.headers['Authorization']=='Bearer test-key'
        return httpx.Response(200,json={'workflow_run_id':'run-1','data':{'status':'succeeded','outputs':{'result':json.dumps({'intent':'life','answer':'有来源时回答','action':'none','parameters':{},'mental':{'emotion_tag':'平稳','emotion_score':80,'risk_level':'low'}})}}})
    config=SimpleNamespace(DIFY_API_BASE='http://dify.test/v1',DIFY_API_TIMEOUT_SECONDS=10,STUDENT_DIFY_KEY=SecretStr('test-key'))
    decision,run_id=StudentAssistantDifyClient(config,httpx.MockTransport(upstream)).run('测试',Principal('student',7))
    assert decision.mental.workflow_run_id==run_id=='run-1'
    assert len(seen)==1
