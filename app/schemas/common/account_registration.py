"""管理员统一开户：四类身份判别联合；不能自选密码或绕过职位映射传角色。"""
from datetime import date
from typing import Annotated,Literal,Union
from pydantic import BaseModel,ConfigDict,Field,model_validator

class StrictRegistrationModel(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class EmployeeRegistrationProfile(StrictRegistrationModel):
    employee_no:str=Field(min_length=1,max_length=32)
    full_name:str=Field(min_length=1,max_length=100)
    department_id:int=Field(gt=0,strict=True)
    position_title:str=Field(min_length=1,max_length=100)
    joined_date:date|None=None
    work_email:str|None=Field(None,max_length=254)

class StudentRegistrationProfile(StrictRegistrationModel):
    student_no:str=Field(min_length=1,max_length=32)
    full_name:str=Field(min_length=1,max_length=100)
    department_id:int=Field(gt=0,strict=True)
    customer_id:int|None=Field(None,gt=0,strict=True)

class CustomerRegistrationProfile(StrictRegistrationModel):
    full_name:str=Field(min_length=1,max_length=100)
    department_id:int=Field(gt=0,strict=True)
    employee_id:int|None=Field(None,gt=0,strict=True)
    phone:str|None=Field(None,min_length=1,max_length=32)
    education_level:str|None=Field(None,max_length=32)
    target_country_code:str|None=Field(None,max_length=8)

class AccountRegistrationBase(StrictRegistrationModel):
    username:str=Field(min_length=1,max_length=64)

class AdminRegistration(AccountRegistrationBase):
    identity_type:Literal['admin']

class EmployeeRegistration(AccountRegistrationBase):
    identity_type:Literal['employee']
    employee_id:int|None=Field(None,gt=0,strict=True)
    profile:EmployeeRegistrationProfile|None=None
    @model_validator(mode='after')
    def exactly_one_source(self):
        if (self.employee_id is None)==(self.profile is None):raise ValueError('employee_id与profile必须且只能提供一个')
        return self

class StudentRegistration(AccountRegistrationBase):
    identity_type:Literal['student']
    student_id:int|None=Field(None,gt=0,strict=True)
    profile:StudentRegistrationProfile|None=None
    @model_validator(mode='after')
    def exactly_one_source(self):
        if (self.student_id is None)==(self.profile is None):raise ValueError('student_id与profile必须且只能提供一个')
        return self

class CustomerRegistration(AccountRegistrationBase):
    identity_type:Literal['customer']
    customer_id:int|None=Field(None,gt=0,strict=True)
    profile:CustomerRegistrationProfile|None=None
    @model_validator(mode='after')
    def exactly_one_source(self):
        if (self.customer_id is None)==(self.profile is None):raise ValueError('customer_id与profile必须且只能提供一个')
        return self

RegistrationRequest=Annotated[Union[AdminRegistration,EmployeeRegistration,StudentRegistration,CustomerRegistration],Field(discriminator='identity_type')]
