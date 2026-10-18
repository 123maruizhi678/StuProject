"""按用户提供的画像文件执行两个教育产品的确定性研判。"""
from datetime import datetime, timezone
from app.schemas.customer.profile import ProfileFacts

SOURCE_SHA256 = 'c5a624a6602ab63f985d0c1f40bacc6c035c39f756d41d8a5caf7d5a6cb50a30'
RULE_VERSION = 'portrait-docx-' + SOURCE_SHA256[:12]
SOURCE_NAME = '用户画像研判规则.docx'
LABELS = {'full_name':'姓名','needs':'实际需求','age':'年龄','education_level':'学历','education_status':'学历状态','grade':'当前年级',
          'preferred_countries':'意向国家','excluded_countries':'明确不考虑的国家','study_abroad_willingness':'留学意愿',
          'education_goal':'升学需求','employment_goal':'就业需求','immigration_goal':'移民需求','family_support':'家庭支持',
          'budget_rmb':'可用预算（人民币）','german_level':'当前德语等级','german_learning_willingness':'德语学习意愿',
          'german_expression_ability':'德语表达能力','practical_ability':'动手能力','logical_ability':'逻辑思维能力',
          'closed_training_willingness':'封闭实训意愿','entrance_test_willingness':'入学测试意愿'}

SG_PATHS = [
    {'name':'2 + 2 新加坡定向培养本科班 / 2 + 2 + 1 本硕连读','audience':'初中毕业生','age_reference':'大致 14—16 岁，超出范围需确认'},
    {'name':'0.5/1 + 2 本科班 / 0.5/1 + 2 + 1 本硕连读','audience':'高二在读、高中及中职中技同等学历毕业生','age_reference':'大约 16—19 岁，超出范围需确认'},
    {'name':'一年制专升本','audience':'国内专科毕业生','age_reference':'文件未规定年龄上限'},
    {'name':'一年制本升硕','audience':'国内本科毕业生','age_reference':'文件未规定年龄上限'},
    {'name':'6 + 6 酒店运营 / 9 + 6 航空运营大专就业班','audience':'职高、中专、中职、技校学生','age_reference':'年龄满 17 岁'},
]


def catalog():
    return {'rule_version':RULE_VERSION, 'source_name':SOURCE_NAME, 'source_sha256':SOURCE_SHA256,
            'field_labels':{key:LABELS[key] for key in ProfileFacts.model_fields},
            'input':{'extensions':['pdf','docx','xlsx','xls','csv','tsv','txt','md'],
                     'max_file_bytes':20*1024*1024,'max_customers':200,'multiple_worksheets':True},
            'interpretation':[
                '新加坡年龄原文为“大致 / 大约”，超出参考范围列为待核实，不直接认定不符合。',
                '新加坡不同学历对应不同路径；不能把某条路径的年龄套用到全部客户。',
                '德国 18—35 岁、高中及以上是明确基础条件；德语 B1 是企业匹配和面试前的阶段要求。',
                '家庭、能力和意愿按已有资料核对；缺失不会当作否定，也不会自动补造。',
                '文件未定义评分权重、总分或预算淘汰线，因此不输出虚构匹配分数。',
                '费用、就业、升学与永居等文件描述仅作原文背景，不作为对客户的办理保证。'],
            'products':[
                {'code':'SG-EDUCATION','name':'新加坡国际本硕升学计划','country':'新加坡','paths':SG_PATHS,
                 'conditions':['学历与相应项目路径匹配','有留学意愿并考虑新加坡','有升学或就业需求','家庭支持和预算需沟通核实'],
                 'milestones':['确认是否愿意参加英语及心理笔试、英语口语及沟通面试'],
                 'reference':'基本属性 1.1、1.2；社会属性 3.1—3.3；其他属性 4.1、4.2'},
                {'code':'DE-VOCATIONAL','name':'中德精英人才共建计划','country':'德国','paths':[],
                 'conditions':['18—35 岁（含边界）','高中或同等学历及以上','有赴德意愿和就业、升学或长期发展需求',
                               '动手与逻辑能力、德语学习及表达、家庭支持、封闭实训意愿需核实'],
                 'milestones':['国内考取德语 B1 后，才能进入德国企业匹配和面试阶段'],
                 'reference':'基本属性；社会属性 2.1—2.4；其他属性'}]}


def education(value):
    text = (value or '').strip()
    lower=text.lower()
    if any(v in lower for v in ('bachelor','master','phd','doctorate')): return '本科'
    if 'associate' in lower: return '专科'
    if 'senior high' in lower or lower=='high school': return '高中'
    if 'junior high' in lower or 'middle school' in lower: return '初中'
    if any(v in text for v in ['博士','硕士','研究生','本科','学士']): return '本科'
    if any(v in text for v in ['大专','专科','高职']): return '专科'
    if any(v in text for v in ['职高','中专','中职','中技','技校','技工']): return '中职'
    if any(v in text for v in ['高中','高二','高三','高一','普高']): return '高中'
    if '初中' in text: return '初中'
    if '小学' in text or '未上学' in text: return '小学'
    return None


def _condition(field, expected, actual, status, reason, kind='required', reference=''):
    return {'field':field, 'label':LABELS.get(field, field), 'expected':expected, 'actual':actual,
            'status':status, 'kind':kind, 'reason':reason, 'reference':reference}


def _bool(facts, field, expected, reference, kind='required'):
    actual=facts.get(field)
    return _condition(field,expected,actual,'missing' if actual is None else 'passed' if actual else 'failed',
                      '资料未说明，需向客户核实' if actual is None else '客户资料明确支持' if actual else '客户资料明确不支持',kind,reference)


def _country(facts,country):
    preferred=facts.get('preferred_countries') or []; excluded=facts.get('excluded_countries') or []
    status='failed' if country in excluded else 'passed' if country in preferred else 'missing'
    return _condition('preferred_countries','考虑'+country,preferred or None,status,
                      '客户明确不考虑'+country if status=='failed' else '已说明意向' if status=='passed' else '未说明对该国家的意愿，需核实',reference='其他属性：留学意愿')


def _need(facts, fields):
    values=[facts.get(k) for k in fields]
    status='passed' if any(v is True for v in values) else 'failed' if all(v is False for v in values) else 'missing'
    return _condition('needs','至少一种需求：'+' / '.join(LABELS[k] for k in fields),
                      {LABELS[k]:facts.get(k) for k in fields},status,
                      '已确认至少一种相关需求' if status=='passed' else '尚未确认客户的实际需求' if status=='missing' else '客户明确没有相关需求',reference='社会属性：教育 / 职业需求')


def _sg_paths(facts):
    level=education(facts.get('education_level')); age=facts.get('age')
    text=(facts.get('education_level') or '')+(facts.get('grade') or '')
    studying=facts.get('education_status')=='在读' or '在读' in text or any(v in text for v in ['高一','高二','高三'])
    paths=[]
    def add(index,status,reason): paths.append({**SG_PATHS[index],'status':status,'reason':reason})
    if level=='初中':
        if studying:add(0,'pending','初中尚未毕业，需要核实毕业时间')
        else:add(0,'eligible' if age is not None and 14<=age<=16 else 'pending','符合初中毕业路径；年龄为参考范围' if age is not None and 14<=age<=16 else '需核实年龄与初中毕业路径的适配，原文年龄不是硬性上限')
    if level in ('高中','中职') and (not studying or '高二' in text):
        add(1,'eligible' if age is not None and 16<=age<=19 else 'pending','符合高中或同等学历路径' if age is not None and 16<=age<=19 else '年龄超出或缺少 16—19 岁参考信息，需向项目方确认')
    if level=='专科':add(2,'pending' if studying else 'eligible','需取得专科毕业资格' if studying else '专科毕业可考虑一年制专升本，文件未另设年龄上限')
    if level=='本科':add(3,'pending' if studying else 'eligible','需取得本科毕业资格' if studying else '本科毕业可关注一年制本升硕，文件未另设年龄上限')
    if level=='中职':add(4,'eligible' if age is not None and age>=17 else 'pending' if age is None else 'ineligible','该路径明确要求年龄满 17 岁')
    if not paths and level=='高中' and studying:add(1,'pending','当前年级 / 毕业状态尚不满足明确描述，需核实高二在读或毕业时间')
    return paths


def _result(product, facts, conditions, paths=None):
    required=[c for c in conditions if c['kind']=='required']
    hard_failed=[c for c in required if c['status']=='failed']
    unresolved=[c for c in required if c['status'] in ('missing','review')]
    # 家庭、能力等画像倾向不足时需要沟通，不直接当作入学拒绝条件。
    supportive=[c for c in conditions if c['kind']=='supportive' and c['status']!='passed']
    status='not_matched' if hard_failed else 'pending' if unresolved or supportive else 'matched'
    missing=[{'field':c['field'],'label':c['label'],'question':c['expected']} for c in conditions
             if c['status'] in ('missing','review') or (c['kind']=='supportive' and c['status']=='failed')]
    steps=[]
    if hard_failed:steps.append('说明当前不符合的画像条件，核实资料后再讨论其他项目。')
    if unresolved or supportive:steps.append('优先核实尚不明确或不一致的意愿、能力与支持条件。')
    steps.extend(c['label']+'：'+c['expected'] for c in unresolved+supportive)
    if product['code']=='DE-VOCATIONAL':
        level=facts.get('german_level');ready=level in ('B1','B2','C1','C2')
        milestones=[{'name':'德国企业匹配及面试','status':'ready' if ready else 'not_ready' if level else 'unknown',
                     'reason':'资料已说明德语达到 B1 或以上，仍需核验证书' if ready else '需在国内取得德语 B1；画像匹配不等于已满足企业匹配条件'}]
    else:
        willing=facts.get('entrance_test_willingness')
        milestones=[{'name':'英语及心理笔试、英语口语及沟通面试','status':'not_ready' if willing is False else 'requires_test' if willing else 'requires_confirmation',
                     'reason':'客户明确不愿参加入学测试，实际入学推进受阻，需要沟通确认' if willing is False else '确认并安排项目入学测试；意愿不能代替考试结果' if willing else '需沟通是否接受入学测试；文件未给出可用于自动判定的分数线'}]
    steps.extend(m['reason'] for m in milestones)
    return {'product_code':product['code'],'product_name':product['name'],'status':status,
            'status_label':{'matched':'符合目标画像','pending':'资料不足 / 待核实','not_matched':'暂不符合目标画像'}[status],
            'conditions':conditions,'paths':paths or [],'missing_information':missing,'milestones':milestones,
            'blocking_reasons':[c['label']+'：'+c['reason'] for c in hard_failed],
            'next_steps':steps,'score':None,'rule_version':RULE_VERSION}


def evaluate_profile(raw):
    facts=ProfileFacts.model_validate(raw).model_dump(exclude_none=True)
    country_conflict=set(facts.get('preferred_countries') or []) & set(facts.get('excluded_countries') or [])
    if country_conflict:
        # 相互冲突的信息不能作为肯定事实。
        facts['preferred_countries']=[x for x in facts.get('preferred_countries',[]) if x not in country_conflict]
        facts['excluded_countries']=[x for x in facts.get('excluded_countries',[]) if x not in country_conflict]
    level=education(facts.get('education_level')); age=facts.get('age'); c=catalog(); sg,de=c['products']
    paths=_sg_paths(facts)
    path_status='passed' if any(p['status']=='eligible' for p in paths) else 'review' if paths else 'failed' if level=='小学' else 'missing'
    sg_conditions=[_condition('education_level','学历、年级与一条新加坡项目路径相符',facts.get('education_level'),path_status,
                             '至少一条路径符合' if path_status=='passed' else '现有信息需要核实对应项目路径',reference='基本属性 1.1、1.2'),
                   _bool(facts,'study_abroad_willingness','愿意出国留学','其他属性 4.1'),_country(facts,'新加坡'),
                   _need(facts,['education_goal','employment_goal']),
                   _bool(facts,'family_support','家庭对留学有经济或其他实际支持','社会属性 3.1','supportive'),
                   _condition('budget_rmb','按路径沟通学费及生活费；没有统一淘汰金额',facts.get('budget_rmb'),'reference',
                              '原文约 25—26 万 / 30—31 万是部分项目学费背景，不作为所有客户的预算硬门槛','reference','社会属性 3.1')]
    age_status='missing' if age is None else 'passed' if 18<=age<=35 else 'failed'
    studying=facts.get('education_status')=='在读' or '在读' in (facts.get('education_level') or '') or any(x in (facts.get('grade') or '')+(facts.get('education_level') or '') for x in ('高一','高二','高三'))
    edu_status='missing' if level is None else 'failed' if level in ('小学','初中') else 'review' if studying and level in ('高中','中职') else 'passed'
    de_conditions=[_condition('age','18—35 岁（含 18 和 35）',age,age_status,'明确的年龄范围','required','基本属性：年龄'),
                   _condition('education_level','高中或同等学历及以上',facts.get('education_level'),edu_status,
                              '资料支持高中或同等学历及以上' if edu_status=='passed' else '高中在读需要核实毕业资格' if edu_status=='review' else '现有学历低于高中或同等学历' if edu_status=='failed' else '学历未提供或无法识别','required','基本属性：学历'),
                   _bool(facts,'study_abroad_willingness','愿意出国留学','其他属性：留学意愿'),_country(facts,'德国'),
                   _need(facts,['employment_goal','education_goal','immigration_goal'])]
    for field,expected,ref in [('practical_ability','具备动手实践能力','社会属性 2.2'),('logical_ability','具备逻辑思维能力','社会属性 2.2'),
                               ('german_learning_willingness','具备德语学习意愿与潜力','社会属性 2.3'),('german_expression_ability','具备一定德语表达能力','社会属性 2.3'),
                               ('family_support','有家庭经济或其他实际支持','社会属性 2.4'),('closed_training_willingness','愿意参加线下封闭实训并接受管理','其他属性：学习态度')]:
        item=_bool(facts,field,expected,ref,'supportive')
        if field in ('german_learning_willingness','german_expression_ability') and facts.get('german_level') in ('B1','B2','C1','C2') and facts.get(field) is None:
            item.update(status='passed',actual=facts['german_level'],reason='资料中的当前德语等级提供相应语言能力依据，证书仍需核实')
        de_conditions.append(item)
    german=facts.get('german_level')
    de_conditions.append(_condition('german_level','企业匹配及面试前，在国内考取德语 B1',german,
        'passed' if german in ('B1','B2','C1','C2') else 'review' if german else 'missing',
        '阶段要求：已有等级仍需核验证书' if german in ('B1','B2','C1','C2') else '尚未说明达到 B1，不能直接进入企业匹配；不单独否定基础画像',
        'milestone','社会属性 2.3'))
    warnings=['意向与排除国家同时出现，已移除冲突值并要求核实：'+'、'.join(sorted(country_conflict))] if country_conflict else []
    return {'rule_version':RULE_VERSION,'source_name':SOURCE_NAME,'source_sha256':SOURCE_SHA256,'facts':facts,
            'evaluated_at':datetime.now(timezone.utc).isoformat(),'warnings':warnings,
            'products':[_result(sg,facts,sg_conditions,paths),_result(de,facts,de_conditions)],
            'notice':'这是目标客户画像研判，不是录取、就业、签证或永居承诺。未提供的资料保持未知。'}
