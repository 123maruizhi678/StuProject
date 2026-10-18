"""Register one existing Dify document through the authorized business API.

Dry-run by default; --apply creates/publishes a knowledge_entry, never a new table.
Credentials are read privately and are not saved or printed.
"""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'.runtime/backend-deps')]
import httpx
from app.clients.enterprise.enterprise_knowledge import DifyKnowledgeClient
from app.core.common.response import BusinessException


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-url',required=True)
    parser.add_argument('--dataset-id',type=uuid.UUID,required=True)
    parser.add_argument('--document-name',required=True)
    audience=parser.add_mutually_exclusive_group(required=True)
    audience.add_argument('--department-id',type=int)
    audience.add_argument('--all-employees',action='store_true')
    parser.add_argument('--username',help='Omit when STUPROJECT_ACCESS_TOKEN is set')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.department_id is not None and args.department_id<=0:parser.error('department-id must be positive')
    dataset=str(args.dataset_id)
    dify=DifyKnowledgeClient()
    matches=[]
    page=1
    while True:
        listing=dify._request('GET',f'/datasets/{dataset}/documents',params={'page':page,'limit':100,'keyword':args.document_name})
        matches.extend(row for row in listing.get('data',[]) if row.get('name')==args.document_name)
        if not listing.get('has_more'):break
        page+=1
    if len(matches)!=1:raise ValueError('Expected exactly one existing Dify document with this name')
    document=str(uuid.UUID(matches[0]['id']))
    reference=f'dify://datasets/{dataset}/documents/{document}'
    dify.document((dataset,document))
    entry_code='DIFY-'+document
    with httpx.Client(base_url=args.backend_url.rstrip('/')+'/',timeout=30,trust_env=False,follow_redirects=False) as client:
        token=os.environ.get('STUPROJECT_ACCESS_TOKEN')
        if not token:
            username=args.username or input('System username: ')
            envelope=client.post('api/v1/auth/login',json={'username':username,'password':getpass.getpass('System password: ')}).json()
            if envelope.get('code')!=0:raise ValueError('System login failed')
            data=envelope.get('data') or {}
            token=data.get('access_token')
        if not token:raise ValueError('No valid system access token')
        client.headers['Authorization']='Bearer '+token

        def api(method,path,**kwargs):
            response=client.request(method,'api/v1/enterprise/'+path,**kwargs)
            response.raise_for_status()
            envelope=response.json()
            if envelope.get('code')!=0:raise ValueError('Business API failed: '+str(envelope.get('message','unknown error')))
            return envelope.get('data')

        permissions=api('GET','me/permissions').get('permissions',[])
        if not {'enterprise.knowledge.manage','enterprise.knowledge.publish'}<=set(permissions):
            raise ValueError('Current account must have knowledge.manage and knowledge.publish')
        existing=[]
        offset=0
        while True:
            listing=api('GET','knowledge',params={'manage':'true','limit':100,'offset':offset})
            rows=listing.get('items',[])
            existing.extend(row for row in rows if row.get('entry_code')==entry_code)
            offset+=len(rows)
            if not rows or offset>=listing.get('total',offset):break
        if len(existing)>1:raise ValueError('Duplicate existing source registrations')
        row=existing[0] if existing else None
        if row and (row.get('source_reference')!=reference or row.get('access_department_id')!=args.department_id):
            raise ValueError('Existing source or audience differs; review it before changing permissions')
        if row and row.get('status')=='disabled':raise ValueError('Source was explicitly disabled; review it before republishing')
        def utc_date(value):
            if not value:return None
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        now=datetime.now(timezone.utc)
        active=bool(row and row.get('status')=='published' and row.get('index_status')=='ready'
            and utc_date(row.get('effective_from')) and utc_date(row['effective_from'])<=now
            and (not row.get('expires_at') or utc_date(row['expires_at'])>now))
        print(json.dumps({'apply':args.apply,'title':args.document_name,'source_reference':reference,
            'access_department_id':args.department_id,'backend':args.backend_url,
            'operation':'reuse published source' if active else 'create/reuse draft and publish'},ensure_ascii=True))
        if not args.apply:return
        if row is None:
            key=str(uuid.uuid5(uuid.NAMESPACE_URL,reference+':register:'+str(args.department_id)))
            row=api('POST','knowledge',headers={'Idempotency-Key':key},json={'entry_code':entry_code,
                'entry_type':'document','title':args.document_name,'source_reference':reference,
                'access_department_id':args.department_id})
        if not active:
            row=api('POST',f"knowledge/{row['knowledge_id']}/publish",headers={'Idempotency-Key':str(uuid.uuid4())},
                json={'expected_version':row['row_version'],'effective_from':datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'registered':True,'knowledge_id':row['knowledge_id'],'status':row['status'],'new_tables':False}))


if __name__=='__main__':
    try:main()
    except (BusinessException,ValueError,httpx.HTTPError) as exc:
        # Avoid tracebacks containing configuration, request headers, or secrets.
        message=exc.message if isinstance(exc,BusinessException) else str(exc) if isinstance(exc,ValueError) else 'Connection to Dify or business backend failed'
        print(message,file=sys.stderr)
        raise SystemExit(1)
