"""公共电话标准化、Fernet加密和HMAC精确检索，同一事实只使用一套密钥。"""
import re,hmac,hashlib
from cryptography.fernet import Fernet
from app.config import settings
from app.core.common.response import BusinessException

def phone_fields(phone):
    if phone is None:return {'phone_ciphertext':None,'phone_lookup_token':None}
    number=re.sub(r'[\s()-]','',phone)
    if not re.fullmatch(r'\+?\d{7,15}',number):raise BusinessException('电话号码格式无效',400)
    if len(number)==11 and number.startswith('1'):number='+86'+number
    elif not number.startswith('+'):number='+'+number
    if not settings.ENTERPRISE_PHONE_ENCRYPTION_KEY or len(settings.ENTERPRISE_PHONE_LOOKUP_SECRET)<32:raise BusinessException('公共电话保护密钥未配置',503)
    return {'phone_ciphertext':Fernet(settings.ENTERPRISE_PHONE_ENCRYPTION_KEY.encode()).encrypt(number.encode()),'phone_lookup_token':hmac.new(settings.ENTERPRISE_PHONE_LOOKUP_SECRET.encode(),number.encode(),hashlib.sha256).hexdigest()}
