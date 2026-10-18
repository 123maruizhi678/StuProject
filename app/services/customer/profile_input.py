"""客户资料抽取与多格式输入；模型只辅助原有基础事实，结论由文件规则决定。"""
import io
import re
from pathlib import Path

from pydantic import ValidationError
from app.schemas.customer.profile import ProfileFacts, PROFILE_FIELDS
from app.services.customer.errors import BadRequestError
from app.services.customer.extractor import ExtractorService
from app.services.customer.profile_rules import evaluate_profile, RULE_VERSION, SOURCE_SHA256, LABELS
from app.services.customer.profile_documents import decode_text, read_docx, read_tables

MAX_FILE_BYTES=20*1024*1024
MAX_ROWS=200
HEADERS={'姓名':'full_name','客户姓名':'full_name','年龄':'age','学历':'education_level','学历状态':'education_status',
         '毕业状态':'education_status','年级':'grade','当前年级':'grade','意向国家':'preferred_countries','目标国家':'preferred_countries',
         '不考虑国家':'excluded_countries','留学意愿':'study_abroad_willingness','升学需求':'education_goal','就业需求':'employment_goal',
         '移民需求':'immigration_goal','家庭支持':'family_support','留学预算':'budget_rmb','预算':'budget_rmb','预算元':'budget_rmb',
         '德语等级':'german_level','当前德语等级':'german_level','德语学习意愿':'german_learning_willingness',
         '德语表达能力':'german_expression_ability','动手能力':'practical_ability','逻辑能力':'logical_ability','逻辑思维':'logical_ability',
         '封闭实训意愿':'closed_training_willingness','入学测试意愿':'entrance_test_willingness'}
HEADERS.update({label:key for key,label in LABELS.items() if key in PROFILE_FIELDS})
HEADERS.update({'名字':'full_name','客户年龄':'age','最高学历':'education_level','学历层次':'education_level',
                '文化程度':'education_level','德语水平':'german_level','是否愿意留学':'study_abroad_willingness',
                '家庭是否支持':'family_support','预算（人民币元）':'budget_rmb','逻辑思维能力':'logical_ability'})
BOOL_FIELDS={k for k,v in ProfileFacts.model_fields.items() if 'bool' in str(v.annotation)}
TRUE={'是','有','愿意','接受','支持','强','具备','可以','同意','yes','true','1','已确认','较强'}
FALSE={'否','无','没有','不愿意','不接受','不支持','弱','不具备','拒绝','no','false','0','不考虑'}


def coerce_profile(raw):
    """逐字段验证，错误值留为未知并产生提示；不得把字符串 False 当真。"""
    result={};warnings=[]
    for key,value in raw.items():
        if key not in PROFILE_FIELDS or value is None or value=='':continue
        try:
            if key in BOOL_FIELDS and not isinstance(value,bool):
                text=str(value).strip().lower()
                value=True if text in TRUE else False if text in FALSE else value
            elif key=='age' and not isinstance(value,bool):
                if isinstance(value,str) and (match:=re.fullmatch(r'(\d+)(?:\.0+)?(?:\s*岁)?',value.strip())):value=int(match[1])
                elif isinstance(value,float) and value.is_integer():value=int(value)
            elif key=='budget_rmb' and not isinstance(value,bool):
                match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(万|万元|元|人民币)?\s*',str(value))
                if match:value=float(match[1])*(10000 if (match[2] or '').startswith('万') else 1)
                elif isinstance(value,int):value=float(value)
            elif key in ('preferred_countries','excluded_countries') and isinstance(value,str):
                parts=[s.strip() for s in re.split(r'[,，、/;；]',value) if s.strip()]
                country_aliases={'singapore':'新加坡','sg':'新加坡','germany':'德国','deutschland':'德国','de':'德国'}
                value=list(dict.fromkeys(country_aliases.get(s.lower(),s) for s in parts))
            elif key=='german_level' and isinstance(value,str):value=value.strip().upper()
            elif key=='education_status' and isinstance(value,str):
                value='毕业' if value.strip() in ('已毕业','毕业','应届毕业','往届毕业') else '在读' if value.strip() in ('在读','未毕业') else value
            valid=ProfileFacts.model_validate({key:value}).model_dump(exclude_none=True)
            result.update(valid)
        except (ValidationError,ValueError,TypeError,OverflowError):warnings.append(f'{HEADERS_REVERSE.get(key,key)}无法可靠识别，已保留为未知')
    return result,warnings


HEADERS_REVERSE={v:k for k,v in HEADERS.items()}


def extract_profile(text, extractor=None):
    if not isinstance(text,str) or not text.strip():raise BadRequestError('没有可解析的客户资料')
    if len(text.encode('utf-8'))>100*1024:raise BadRequestError('文本超过 100 KiB，请拆分客户资料后提交')
    core=(extractor or ExtractorService()).extract(text)
    raw={k:v for k,v in core.items() if k in PROFILE_FIELDS}
    warnings=[]
    # 标签值优先，重复且冲突的标签不会静默选择第一项。
    aliases={**HEADERS, **{key:key for key in PROFILE_FIELDS}}
    labeled={};conflicts=set()
    label_pattern=re.compile(r'(?<![\w\u4e00-\u9fff])('+ '|'.join(re.escape(a) for a in sorted(aliases,key=len,reverse=True)) +r')\s*[:：]\s*')
    matches=list(label_pattern.finditer(text))
    for index,match in enumerate(matches):
        key=aliases[match[1]]
        end=matches[index+1].start() if index+1<len(matches) else len(text)
        value=re.split(r'[;；。\n]',text[match.end():end],maxsplit=1)[0].strip(' ，,\t\r')
        if key not in ('preferred_countries','excluded_countries'):
            value=re.split(r'[,，]',value,maxsplit=1)[0].strip()
        if value:labeled.setdefault(key,[]).append(value)
    for key,found in labeled.items():
        values=list(dict.fromkeys(found))
        if key=='full_name' and len(values)>1:
            raise BadRequestError('资料包含多个不同客户姓名，请分别提交简历或整理为 Excel 一人一行')
        normalized=[coerce_profile({key:value})[0].get(key,value) for value in values]
        if any(value!=normalized[0] for value in normalized[1:]):
            raw.pop(key,None);conflicts.add(key);warnings.append(HEADERS_REVERSE.get(key,key)+'有多处冲突描述，请人工核实');continue
        raw[key]=values[0]
    ages=list(dict.fromkeys(int(n) for n in re.findall(r'(?<!\d)(\d{1,3})\s*岁',text)))
    if len(ages)>1:raw.pop('age',None);warnings.append('出现多个不同年龄，需核实客户信息')
    elif 'age' not in raw and 'age' not in conflicts and len(ages)==1:raw['age']=ages[0]
    if 'education_level' not in raw and 'education_level' not in conflicts:
        found=re.findall(r'初中毕业|高中毕业|高二在读|高二|中专(?:毕业|在读)?|中职(?:毕业|在读)?|职高(?:毕业|在读)?|技校(?:毕业|在读)?|大专(?:毕业|在读)?|专科(?:毕业|在读)?|本科(?:毕业|在读)?|硕士(?:毕业|在读)?|博士(?:毕业|在读)?',text)
        if len(set(found))==1:raw['education_level']=found[0]
    education=raw.get('education_level','')
    if isinstance(education,str):
        if '在读' in education or '高二' in education:raw.setdefault('education_status','在读')
        elif '毕业' in education:raw.setdefault('education_status','毕业')
        if '高二' in education:raw.setdefault('grade','高二')
    # 只识别明确说出的意愿，不根据年龄、职业或收入猜测。
    patterns={
      'study_abroad_willingness':(r'不(?:愿意|想|打算|希望)(?:出国|留学)|不考虑留学|拒绝出国',r'(?:愿意|希望|想要|计划|打算)(?:出国|赴(?:德|新加坡)|去(?:德国|新加坡)|留学)|想去(?:德国|新加坡)(?:留学|读书|学习)'),
      'education_goal':(r'没有升学需求|不(?:想|希望|考虑|需要)(?:升学|提升学历)|拒绝专升本|拒绝本升硕',r'希望升学|提升学历|希望专升本|计划专升本|希望本升硕|计划本升硕|申请硕士|攻读本科'),
      'employment_goal':(r'没有就业需求|不(?:想|希望|考虑|需要)(?:就业|找工作)',r'希望就业|稳定工作|就业发展|找工作|职业发展|就业需求明确'),
      'immigration_goal':(r'不考虑移民|没有移民需求',r'希望移民|希望长期在德国生活|移民需求明确'),
      'family_support':(r'家(?:庭|人|长)不支持',r'家(?:庭|人|长)(?:愿意)?支持'),
      'german_learning_willingness':(r'不愿意学(?:习)?德语|拒绝学习德语',r'愿意学(?:习)?德语|正在学(?:习)?德语'),
      'german_expression_ability':(r'无法用德语表达|不会德语表达',r'可以用德语交流|具备德语表达能力'),
      'practical_ability':(r'动手能力(?:较)?弱|不擅长动手',r'动手能力(?:较)?强|擅长动手'),
      'logical_ability':(r'逻辑(?:思维|能力)(?:较)?弱',r'逻辑(?:思维|能力)(?:较)?强'),
      'closed_training_willingness':(r'不(?:接受|愿意参加)封闭(?:式)?实训|拒绝封闭(?:式)?实训',r'愿意参加(?:线下)?封闭(?:式)?实训|接受封闭(?:式)?实训'),
      'entrance_test_willingness':(r'不接受入学测试|拒绝入学测试',r'愿意参加入学测试|接受入学测试')}
    narrative_text=label_pattern.sub('',text)
    for field,(negative,positive) in patterns.items():
        if field in conflicts:continue
        negative_matches=list(re.finditer(negative,narrative_text))
        yes=any(narrative_text[max(0,m.start()-1):m.start()] not in ('不','没','未')
                and not any(n.start()<=m.start()<n.end() for n in negative_matches) for m in re.finditer(positive,narrative_text))
        previous=coerce_profile({field:raw[field]})[0].get(field) if field in raw else None
        if negative_matches and yes:
            raw.pop(field,None)
            conflicts.add(field)
            warnings.append(HEADERS_REVERSE.get(field,field)+'同时出现肯定与否定描述，请人工核实')
        elif (negative_matches and previous is True) or (yes and previous is False):
            raw.pop(field,None)
            conflicts.add(field)
            warnings.append(HEADERS_REVERSE.get(field,field)+'标签与正文描述冲突，请人工核实')
        elif field not in raw:
            if negative_matches:raw[field]=False
            elif yes:raw[field]=True
    if 'preferred_countries' not in raw and 'preferred_countries' not in conflicts:
        countries=[]
        for country in ('新加坡','德国'):
            for match in re.finditer(r'(?:意向|考虑|希望去|想去|愿意去|计划去|希望赴|愿赴|希望留学|希望到|计划赴|愿意赴|打算去)\s*'+country,text):
                if text[max(0,match.start()-1):match.start()] not in ('不','无'):countries.append(country);break
        if countries:raw['preferred_countries']=countries
    exclusions=[country for country in ('新加坡','德国') if re.search(r'(?:不考虑|不想去|不愿去|拒绝去)\s*'+country,text)]
    if exclusions:raw['excluded_countries']=list(dict.fromkeys([*(raw.get('excluded_countries') if isinstance(raw.get('excluded_countries'),list) else [v for v in re.split(r'[,，、/;；]',raw.get('excluded_countries','')) if v]),*exclusions]))
    if 'study_abroad_willingness' not in raw and 'study_abroad_willingness' not in conflicts:
        if any(text[max(0,m.start()-1):m.start()] not in ('不','没','未') for m in re.finditer(r'(?:希望|计划|愿意|打算|想)\s*(?:去|赴|到)\s*(?:德国|新加坡)\s*(?:留学|读书|学习|升学|就业|工作)',text)):
            raw['study_abroad_willingness']=True
    if 'german_level' not in raw and 'german_level' not in conflicts:
        for match in re.finditer(r'德语\s*(?:等级|水平|证书)?\s*[:：]?\s*(A[012]|B[12]|C[12])',text,re.I):
            prefix=text[max(0,match.start()-12):match.start()]
            suffix=text[match.end():match.end()+8]
            if not re.search(r'目标|计划|准备|备考|希望达到|将要|争取|未达到|没达到|没有|尚未|未取得|未考取|未通过',prefix) and not re.match(r'\s*(?:目标|未通过|没通过|未考过|备考)',suffix):raw['german_level']=match[1].upper()
    facts,invalid=coerce_profile(raw)
    if not facts:raise BadRequestError('未识别到可用于画像研判的事实，请补充姓名、年龄、学历或意向等资料')
    return facts,warnings+invalid


def parse_input(*,text=None,file_name=None,file_bytes=None,extractor=None):
    if file_bytes is not None:
        if text and text.strip():raise BadRequestError('请单独提交文本或文件，不要混合两个客户来源')
        if not file_bytes:raise BadRequestError('上传文件为空')
        if len(file_bytes)>MAX_FILE_BYTES:raise BadRequestError('文件超过 20 MB，请拆分后上传')
        suffix=Path(file_name or '').suffix.lower()
        if suffix not in ('.txt','.md','.pdf','.docx','.xlsx','.xls','.csv','.tsv'):raise BadRequestError('支持文本、PDF、DOCX、XLSX、XLS、CSV、TSV、TXT、MD；旧版 DOC 请另存为 DOCX')
        if suffix in ('.xlsx','.xls','.csv','.tsv'):
            results=[]
            rows,table_warnings=read_tables(file_bytes,suffix,HEADERS,PROFILE_FIELDS,MAX_ROWS)
            for sheet,index,raw in rows:
                facts,warnings=coerce_profile(raw)
                results.append({'row_number':index,'sheet_name':sheet,'facts':facts,'warnings':table_warnings+warnings,'error':None if facts else '该行未识别到有效客户事实'})
            return results
        if suffix=='.pdf':
            from pypdf import PdfReader
            try:
                pdf=PdfReader(io.BytesIO(file_bytes))
                if len(pdf.pages)>100:raise BadRequestError('PDF 超过 100 页，请拆分简历')
                text='\n'.join(page.extract_text() or '' for page in pdf.pages)
            except BadRequestError:raise
            except Exception as exc:raise BadRequestError('PDF 无法读取，可能已加密或损坏') from exc
            if not text.strip():raise BadRequestError('PDF 没有可提取的文字层；扫描简历请先 OCR 转成文字或补充文本')
        elif suffix=='.docx':text=read_docx(file_bytes,set(HEADERS)|PROFILE_FIELDS)
        else:text=decode_text(file_bytes)
    # 不把多份简历文本混成同一客户。
    if len(set(re.findall(r'客户([一二三四五六七八九十0-9]+)\s*[:：]',text or '')))>1:
        raise BadRequestError('文本包含多位客户，请分别提交或整理成 Excel 一人一行')
    facts,warnings=extract_profile(text,extractor)
    return [{'row_number':1,'facts':facts,'warnings':warnings,'error':None}]


def preview_input(**kwargs):
    rows=parse_input(**kwargs);items=[]
    for row in rows:
        item={**row,'evaluation':None}
        if not row['error']:item['evaluation']=evaluate_profile(row['facts'])
        items.append(item)
    counts={product:{status:0 for status in ('matched','pending','not_matched')} for product in ('SG-EDUCATION','DE-VOCATIONAL')}
    for item in items:
        for product in (item.get('evaluation') or {}).get('products',[]):counts[product['product_code']][product['status']]+=1
    return {'rule_version':RULE_VERSION,'source_sha256':SOURCE_SHA256,'items':items,'total':len(items),
            'success_count':sum(not r['error'] for r in items),'failed_count':sum(bool(r['error']) for r in items),
            'summary':counts,'persisted':False}
