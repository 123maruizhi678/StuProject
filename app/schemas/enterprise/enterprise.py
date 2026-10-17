"""企业请求白名单；未声明字段禁止通过批量赋值写入。"""
from datetime import date,datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Mutation(StrictModel):
    expected_version:int|None=Field(None,ge=1)
    reason:str|None=Field(None,min_length=1,max_length=1000)
class CustomerCreate(StrictModel):
    full_name:str=Field(min_length=1,max_length=100)
    phone:str|None=Field(None,max_length=32)
    education_level:str|None=Field(None,max_length=32)
    target_country_code:str|None=Field(None,max_length=8)
    employee_id:int|None=Field(None,gt=0)
class PhoneCandidates(StrictModel):
    phone:str=Field(min_length=1,max_length=32)
class CustomerUpdate(Mutation):
    full_name:str|None=Field(None,min_length=1,max_length=100)
    phone:str|None=Field(None,max_length=32)
    education_level:str|None=Field(None,max_length=32)
    target_country_code:str|None=Field(None,max_length=8)
class StatusUpdate(Mutation):
    status:Literal['new','contacting','qualified','signed','lost']
    lost_reason:str|None=Field(None,max_length=3000)
class Assignment(Mutation):
    employee_id:int=Field(gt=0)
    reason:str=Field(min_length=1,max_length=1000)
class FollowupCreate(StrictModel):
    content:str=Field(min_length=1,max_length=10000)
    channel:str=Field(min_length=1,max_length=32)
    followup_at:datetime
    next_followup_at:datetime|None=None
class ScheduleUpdate(Mutation):
    followup_status:Literal['pending','done','cancelled']
    next_followup_at:datetime|None=None
class DailyCreate(StrictModel):
    report_date:date
    submitted_content:str=Field(min_length=1,max_length=20000)
class DailyUpdate(Mutation):
    submitted_content:str=Field(min_length=1,max_length=20000)
class ScoreCreate(StrictModel):
    student_id:int=Field(gt=0)
    course_code:str=Field(min_length=1,max_length=64)
    term_code:str=Field(min_length=1,max_length=32)
    assessment_code:str=Field(min_length=1,max_length=64)
    attempt_no:int=Field(1,ge=1)
    score_value:float=Field(ge=0,allow_inf_nan=False)
    max_score:float=Field(gt=0,allow_inf_nan=False)
class ScoreUpdate(Mutation):
    score_value:float=Field(ge=0,allow_inf_nan=False)
    max_score:float=Field(gt=0,allow_inf_nan=False)
    reason:str=Field(min_length=1,max_length=1000)
class TicketRecord(Mutation):
    content:str=Field(min_length=1,max_length=10000)
    visibility:Literal['student_visible','internal']='student_visible'
class DepartmentCreate(StrictModel):
    department_code:str=Field(min_length=1,max_length=32)
    department_name:str=Field(min_length=1,max_length=100)
    parent_department_id:int|None=Field(None,gt=0)
    function_description:str|None=Field(None,max_length=10000)
class DepartmentUpdate(Mutation):
    department_name:str|None=Field(None,min_length=1,max_length=100)
    parent_department_id:int|None=Field(None,gt=0)
    function_description:str|None=Field(None,max_length=10000)
class EmployeeCreate(StrictModel):
    employee_no:str=Field(min_length=1,max_length=32)
    full_name:str=Field(min_length=1,max_length=100)
    department_id:int=Field(gt=0)
    login_provider:str=Field(min_length=1,max_length=32)
    login_subject:str=Field(min_length=1,max_length=128)
    joined_date:date
    position_title:str|None=Field(None,max_length=100)
    work_email:str|None=Field(None,max_length=254)
class EmployeeUpdate(Mutation):
    full_name:str|None=Field(None,min_length=1,max_length=100)
    position_title:str|None=Field(None,max_length=100)
    work_email:str|None=Field(None,max_length=254)
    status:Literal['active','disabled','left']|None=None
    left_date:date|None=None
class RoleUpdate(Mutation):
    role_codes:list[Literal['employee','consultant','manager','teacher','academic','admin','analyst','reviewer']]=Field(min_length=1,max_length=8)
    reason:str=Field(min_length=1,max_length=1000)
class BindingCreate(StrictModel):
    student_id:int=Field(gt=0)
    employee_id:int=Field(gt=0)
    relation_type:Literal['class_teacher','score_editor','service_advisor']
    course_scope_code:str|None=Field(None,max_length=64)
    is_primary:bool=False
    valid_from:datetime
    valid_to:datetime|None=None
class BindingUpdate(Mutation):
    is_primary:bool|None=None
    course_scope_code:str|None=Field(None,max_length=64)
    valid_to:datetime|None=None
class KnowledgeCreate(StrictModel):
    entry_code:str=Field(min_length=1,max_length=64)
    entry_type:Literal['faq','document']
    title:str=Field(min_length=1,max_length=200)
    question:str|None=Field(None,max_length=10000)
    answer:str|None=Field(None,max_length=30000)
    content_text:str|None=Field(None,max_length=100000)
    access_department_id:int|None=Field(None,gt=0)
    source_reference:str|None=Field(None,max_length=512)
class KnowledgeUpdate(Mutation):
    title:str|None=Field(None,min_length=1,max_length=200)
    question:str|None=Field(None,max_length=10000)
    answer:str|None=Field(None,max_length=30000)
    content_text:str|None=Field(None,max_length=100000)
    source_reference:str|None=Field(None,max_length=512)
class KnowledgePublish(Mutation):
    effective_from:datetime
    expires_at:datetime|None=None
class TextRequest(StrictModel):
    text:str=Field(min_length=1,max_length=10000)
class KnowledgeQuestion(StrictModel):
    question:str=Field(min_length=1,max_length=2000)
class QueryRequest(KnowledgeQuestion):
    filters:dict=Field(default_factory=dict)
class ConfirmRequest(StrictModel):
    token:str=Field(min_length=1,max_length=5000)
    action:str
    target:dict=Field(default_factory=dict)
    fields:dict
class SummaryRequest(StrictModel):
    report_id:int=Field(gt=0)

class CourseCreate(StrictModel):
    course_code:str=Field(min_length=1,max_length=64)
    course_name:str=Field(min_length=1,max_length=200)
class CourseUpdate(Mutation):
    course_name:str|None=Field(None,min_length=1,max_length=200)
    status:Literal['active','disabled']|None=None
class EnrollmentCreate(StrictModel):
    student_id:int=Field(gt=0)
    course_code:str=Field(min_length=1,max_length=64)
    term_code:str=Field(min_length=1,max_length=32)
class EnrollmentUpdate(Mutation):
    status:Literal['active','disabled']
class AcademicCreate(StrictModel):
    student_id:int=Field(gt=0)
    event_type:Literal['exam','ddl']
    title:str=Field(min_length=1,max_length=200)
    due_at:datetime
class AcademicUpdate(StrictModel):
    expected_event_version:int=Field(ge=1)
    title:str|None=Field(None,min_length=1,max_length=200)
    due_at:datetime|None=None
    event_status:Literal['active','cancelled']|None=None
    reason:str=Field(min_length=1,max_length=1000)
class ProgressCreate(StrictModel):
    student_id:int=Field(gt=0)
    application_name:str=Field(min_length=1,max_length=200)
    stage_code:Literal['document_review','school_application','visa_process']
    stage_status:Literal['pending','in_progress','completed','blocked','cancelled']
    detail:str|None=Field(None,max_length=500)
class ProgressUpdate(Mutation):
    stage_status:Literal['pending','in_progress','completed','blocked','cancelled']
    detail:str|None=Field(None,max_length=500)
    reason:str=Field(min_length=1,max_length=1000)
