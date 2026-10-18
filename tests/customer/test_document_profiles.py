"""文件画像回归；不连接真实数据库、Dify 或鉴权后端。"""
import io
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.clients.customer.extract_dify import ExtractDifyClient
from app.services.customer.errors import BadRequestError
from app.services.customer.profile_input import coerce_profile, extract_profile, parse_input, preview_input
from app.services.customer.profile_rules import RULE_VERSION, SOURCE_SHA256, catalog, evaluate_profile
from app.services.customer import profile_app


@pytest.fixture(autouse=True)
def no_external_model(monkeypatch):
    monkeypatch.setattr(ExtractDifyClient,'extract_fields',lambda *a,**kw:None)


def sg(**override):
    return {**dict(full_name='演示甲',age=18,education_level='高中毕业',preferred_countries=['新加坡'],study_abroad_willingness=True,education_goal=True,family_support=True),**override}


def de(**override):
    return {**dict(full_name='演示乙',age=24,education_level='本科',preferred_countries=['德国'],study_abroad_willingness=True,employment_goal=True,family_support=True,
                  practical_ability=True,logical_ability=True,german_learning_willingness=True,german_expression_ability=True,closed_training_willingness=True,german_level='A2'),**override}


def product(facts,index):return evaluate_profile(facts)['products'][index]


def test_document_catalog_is_educational_and_has_file_fingerprint():
    data=catalog();assert data['source_sha256']==SOURCE_SHA256
    assert [p['name'] for p in data['products']]==['新加坡国际本硕升学计划','中德精英人才共建计划']
    assert '理财' not in str(data) and '养老险' not in str(data)
    assert len(data['products'][0]['paths'])==5


@pytest.mark.parametrize('age', [18,35])
def test_german_age_boundaries_included(age):assert product(de(age=age),1)['status']=='matched'


@pytest.mark.parametrize('age',[17,36])
def test_german_outside_age_rejected(age):assert product(de(age=age),1)['status']=='not_matched'


def test_missing_data_never_becomes_a_pass_or_explicit_failure():
    assert [p['status'] for p in evaluate_profile({})['products']]==['pending','pending']
    result=product(de(age=None,german_level=None,logical_ability=None),1)
    assert result['status']=='pending' and any(x['field']=='age' for x in result['missing_information'])


def test_german_junior_education_fails():assert product(de(education_level='初中'),1)['status']=='not_matched'


def test_high_school_grade2_is_pending_for_german_diploma():assert product(de(education_level='高中',grade='高二'),1)['status']=='pending'


def test_b1_is_a_stage_gate_not_invented_profile_rejection():
    a2=product(de(),1);b1=product(de(german_level='B1'),1)
    assert a2['status']==b1['status']=='matched'
    assert a2['milestones'][0]['status']=='not_ready'
    assert b1['milestones'][0]['status']=='ready'
    assert a2['score'] is None


def test_german_family_or_skill_concern_needs_discussion():
    assert product(de(practical_ability=False),1)['status']=='pending'
    assert product(de(family_support=False),1)['status']=='pending'


def test_explicit_country_refusal_and_no_study_intent_fail():
    assert product(de(preferred_countries=[],excluded_countries=['德国']),1)['status']=='not_matched'
    assert product(sg(study_abroad_willingness=False),0)['status']=='not_matched'


def test_conflicting_country_is_unknown_not_silently_passed():
    result=evaluate_profile(de(excluded_countries=['德国']))
    assert result['products'][1]['status']=='pending' and result['warnings']


@pytest.mark.parametrize('education,age,path', [('初中毕业',15,'2 + 2'),('高二在读',16,'0.5/1'),('高中毕业',19,'0.5/1'),('专科毕业',42,'专升本'),('本科毕业',46,'本升硕')])
def test_singapore_routes_follow_education(education,age,path):
    result=product(sg(education_level=education,age=age),0)
    assert result['status']=='matched' and any(path in p['name'] and p['status']=='eligible' for p in result['paths'])


def test_singapore_approximate_age_is_review_not_hard_rejection():
    assert product(sg(education_level='初中毕业',age=17),0)['status']=='pending'


def test_vocational_17_year_rule_only_applies_to_that_path():
    younger=product(sg(education_level='中专毕业',age=16),0)
    assert younger['status']=='matched'
    assert next(p for p in younger['paths'] if '酒店' in p['name'])['status']=='ineligible'
    older=product(sg(education_level='职高在读',age=17),0)
    assert any('酒店' in p['name'] and p['status']=='eligible' for p in older['paths'])


def test_budget_does_not_create_an_unspecified_cutoff():
    assert product(sg(budget_rmb=1000.0),0)['status']=='matched'
    assert product(sg(),0)['status']=='matched'


def test_two_products_are_evaluated_independently():
    result=evaluate_profile(sg(age=16))
    assert result['products'][0]['status']=='matched' and result['products'][1]['status']=='not_matched'


def test_labeled_text_and_boolean_false():
    facts,warnings=extract_profile('姓名：小林；年龄：18；学历：高中毕业；意向国家：新加坡；留学意愿：是；升学需求：是；家庭支持：是；预算：30万元。')
    assert facts['full_name']=='小林' and facts['budget_rmb']==300000
    assert product(facts,0)['status']=='matched'
    facts,_=extract_profile('年龄：24；学历：本科；留学意愿：否；家庭支持：false；封闭实训意愿：否')
    assert facts['study_abroad_willingness'] is False and facts['family_support'] is False


def test_natural_language_refusal_and_target_language_not_achievement():
    facts,_=extract_profile('24岁，本科毕业，不考虑德国，不愿意学习德语，计划考取德语B1，希望就业。')
    assert facts['excluded_countries']==['德国'] and '德国' not in facts.get('preferred_countries',[])
    assert facts['german_learning_willingness'] is False and 'german_level' not in facts


def test_conflicting_ages_do_not_use_first_age():
    facts,warnings=extract_profile('姓名：甲；18岁，另一处写35岁；学历：本科')
    assert 'age' not in facts and warnings


def test_conflicting_alias_labels_stay_unknown():
    facts,warnings=extract_profile('姓名：甲；学历：初中；最高学历：本科；家庭支持：是；家庭支持：否')
    assert 'education_level' not in facts and 'family_support' not in facts and len(warnings)>=2


def test_csv_style_integral_age_and_english_country():
    facts,warnings=coerce_profile({'age':'24.0','preferred_countries':'Germany','german_level':'b1'})
    assert facts=={'age':24,'preferred_countries':['德国'],'german_level':'B1'} and not warnings


def test_wrong_types_are_unknown_with_warnings():
    facts,warnings=coerce_profile({'age':True,'family_support':'也许','german_level':'目标B1','budget_rmb':'不确定','education_level':'高中'})
    assert facts=={'education_level':'高中'} and len(warnings)==4


def workbook(rows):
    book=openpyxl.Workbook();sheet=book.active
    for row in rows:sheet.append(row)
    out=io.BytesIO();book.save(out);book.close();return out.getvalue()


def test_excel_one_customer_per_row_and_original_row_number():
    data=workbook([['姓名','年龄','学历','意向国家','留学意愿','升学需求','家庭支持'],['甲',18,'高中毕业','新加坡','是','是','是'],[None]*7,[None,'不详',None,None,None,None,None]])
    result=preview_input(file_name='客户.xlsx',file_bytes=data)
    assert result['total']==2 and result['failed_count']==1 and result['items'][1]['row_number']==4
    assert result['items'][0]['evaluation']['products'][0]['status']=='matched'


def test_csv_utf8_bom_and_chinese_headers():
    result=preview_input(file_name='客户.csv',file_bytes='\ufeff姓名,年龄,学历\n甲,24,本科\n乙,17,初中'.encode())
    assert result['total']==2 and result['items'][1]['evaluation']['products'][1]['status']=='not_matched'


def test_catalog_template_headers_round_trip_all_facts():
    import csv
    facts=de(budget_rmb=300000.0)
    labels=catalog()['field_labels'];out=io.StringIO();writer=csv.writer(out)
    writer.writerow([labels[k] for k in facts])
    writer.writerow(['是' if v is True else '否' if v is False else '、'.join(v) if isinstance(v,list) else v for v in facts.values()])
    result=preview_input(file_name='客户模板.csv',file_bytes=out.getvalue().encode())
    assert result['items'][0]['facts']==facts
    assert result['items'][0]['evaluation']['products'][1]['status']=='matched'


def pdf(text=None):
    writer=PdfWriter();page=writer.add_blank_page(width=595,height=842)
    if text:
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
        content=DecodedStreamObject();content.set_data(('BT /F1 12 Tf 50 760 Td ('+text+') Tj ET').encode())
        page[NameObject('/Contents')]=writer._add_object(content)
    buffer=io.BytesIO();writer.write(buffer);return buffer.getvalue()


def test_pdf_resume_text_is_extracted_and_evaluated():
    result=preview_input(file_name='resume.pdf',file_bytes=pdf('full_name: Alex; age: 24; education_level: bachelor'))
    assert result['items'][0]['facts']=={'full_name':'Alex','age':24,'education_level':'bachelor'}
    assert len(result['items'][0]['evaluation']['products'])==2


def test_scanned_pdf_returns_actionable_failure():
    with pytest.raises(BadRequestError,match='OCR'):preview_input(file_name='scan.pdf',file_bytes=pdf())


@pytest.mark.parametrize('kwargs',[
    {'text':'客户一：张甲，18岁；客户二：李乙，24岁'},
    {'text':'资料','file_name':'x.txt','file_bytes':b'data'},
    {'file_name':'x.xls','file_bytes':b'not an xlsx'},
    {'file_name':'x.csv','file_bytes':b'unknown\nvalue'},
    {'file_name':'x.csv','file_bytes':'姓名,full_name\n甲,乙'.encode()},
    {'file_name':'x.txt','file_bytes':b''},
])
def test_bad_inputs_are_not_reported_as_success(kwargs):
    with pytest.raises(BadRequestError):preview_input(**kwargs)


def test_row_limit_is_enforced():
    data='姓名,年龄\n'+'\n'.join(f'客户{i},24' for i in range(201))
    with pytest.raises(BadRequestError,match='200'):preview_input(file_name='x.csv',file_bytes=data.encode())


@pytest.fixture
def client(monkeypatch):
    def remote(path,token):
        assert token=='Bearer mock-token'
        if path.endswith('/auth/me/access'):return {'identity_type':'admin','permissions':['customer.rule.read','customer.judge.create','customer.source.read']}
        if path.endswith('/source/1'):return {'source':{'id':1},'fields':[{'id':2,**sg(),'phone_lookup_token':'must-not-return'}]}
        raise AssertionError('Unexpected upstream request')
    monkeypatch.setattr(profile_app,'remote_get',remote)
    with TestClient(profile_app.app) as test:yield test


def test_isolated_api_requires_existing_login(client):
    assert client.get('/api/v1/customer/profile/catalog').status_code==401


def test_api_catalog_analyze_and_structured_reevaluation(client):
    headers={'Authorization':'Bearer mock-token'}
    assert client.get('/api/v1/customer/profile/catalog',headers=headers).json()['data']['rule_version']==RULE_VERSION
    response=client.post('/api/v1/customer/profile/analyze',data={'text':'姓名：甲；年龄：18；学历：高中毕业；留学意愿：是；意向国家：新加坡；升学需求：是；家庭支持：是'},headers=headers)
    assert response.status_code==200 and response.json()['data']['items'][0]['evaluation']['products'][0]['status']=='matched'
    assert client.post('/api/v1/customer/profile/evaluate',json={'facts':de()},headers=headers).json()['data']['products'][1]['status']=='matched'
    assert client.post('/api/v1/customer/profile/evaluate',json={'facts':{'age':True}},headers=headers).status_code==422


def test_api_source_scope_delegated_to_existing_backend_and_contact_not_returned(client):
    response=client.get('/api/v1/customer/source/1/profile',headers={'Authorization':'Bearer mock-token'})
    assert response.status_code==200 and 'must-not-return' not in response.text


def test_readonly_account_cannot_analyze(client,monkeypatch):
    monkeypatch.setattr(profile_app,'remote_get',lambda *args:{'identity_type':'employee','permissions':['customer.rule.read','customer.source.read']})
    assert client.post('/api/v1/customer/profile/analyze',data={'text':'18岁'},headers={'Authorization':'Bearer mock-token'}).status_code==403


def test_cors_only_permits_configured_frontend(client):
    headers={'Origin':'http://192.168.5.13:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'}
    assert client.options('/api/v1/customer/profile/analyze',headers=headers).headers['access-control-allow-origin']=='http://192.168.5.13:5173'
    headers['Origin']='https://unrelated.example'
    assert 'access-control-allow-origin' not in client.options('/api/v1/customer/profile/analyze',headers=headers).headers


def test_saved_file_can_be_read_with_original_permission_and_new_rules(client,monkeypatch):
    def remote(path,token):
        if path.endswith('/auth/me/access'):return {'identity_type':'admin','permissions':['customer.source.read','customer.source.file']}
        return {'source':{'id':1,'file_name':'客户.csv','status':'pending'},'fields':[]}
    monkeypatch.setattr(profile_app,'remote_get',remote)
    seen=[]
    def file(source_id,token):
        seen.append(source_id)
        return '姓名,年龄,学历,意向国家,留学意愿,升学需求,家庭支持\n甲,18,高中毕业,新加坡,是,是,是'.encode()
    monkeypatch.setattr(profile_app,'remote_file',file)
    response=client.get('/api/v1/customer/source/1/profile',headers={'Authorization':'Bearer mock-token'})
    assert seen==[1] and response.json()['data']['items'][0]['evaluation']['products'][0]['status']=='matched'


def test_source_reader_without_file_permission_does_not_download_original(client,monkeypatch):
    def remote(path,token):
        if path.endswith('/auth/me/access'):return {'identity_type':'employee','permissions':['customer.source.read']}
        return {'source':{'id':1,'file_name':'客户.csv'},'fields':[{'id':2,'age':24,'education_level':'本科'}]}
    monkeypatch.setattr(profile_app,'remote_get',remote)
    monkeypatch.setattr(profile_app,'remote_file',lambda *args:pytest.fail('must not download without original-file permission'))
    assert client.get('/api/v1/customer/source/1/profile',headers={'Authorization':'Bearer mock-token'}).status_code==200


def test_local_service_does_not_connect_local_business_database(client,monkeypatch):
    from app.database import engine
    monkeypatch.setattr(engine,'connect',lambda *args,**kwargs:pytest.fail('local profile service must not connect local database'))
    assert client.get('/health').status_code==200
    assert client.get('/api/v1/customer/profile/catalog',headers={'Authorization':'Bearer mock-token'}).status_code==200
    assert client.post('/api/v1/customer/profile/evaluate',json={'facts':sg()},headers={'Authorization':'Bearer mock-token'}).status_code==200
