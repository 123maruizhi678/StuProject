"""Read-only MySQL verification of business records created through the frontend."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sqlalchemy import select
from app.database import engine
from app.models import common as t, enterprise as own
from app.services.common.auth_service import verify_password


def main():
    directory = ROOT / '.runtime/role-simulation'
    run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    ids, accounts = run['ids'], run['accounts']
    refresh_path = directory / 'ui-refresh.json'
    refresh = json.loads(refresh_path.read_text(encoding='utf-8')) if refresh_path.exists() else None
    checks, snapshot = [], {}

    def check(name, work):
        try:
            work()
            checks.append({'name': name, 'status': 'passed'})
        except Exception as exc:
            checks.append({'name': name, 'status': 'failed', 'reason': str(exc)})
        print(checks[-1]['status'].upper(), name, checks[-1].get('reason', ''), flush=True)

    def equal(actual, expected):
        assert actual == expected, f'{actual!r} != {expected!r}'

    with engine.connect() as db:
        # MySQL itself forbids business writes during this verification.
        db.exec_driver_sql('START TRANSACTION READ ONLY')

        def row(table, key, value, fields=None):
            result = db.execute(select(table).where(table.c[key] == value)).mappings().one()
            if fields:
                snapshot[f'{table.name}:{value}'] = {field: result[field] for field in fields}
            return result

        def fields_equal(table, key, value, expected):
            record = row(table, key, value, expected)
            for field, expected_value in expected.items():
                equal(record[field], expected_value)
            return record

        check('root administrator password and identity', lambda: (
            equal(row(t.UserAccount.__table__, 'username', 'root')['identity_type'], 'admin'),
            equal(verify_password('root', row(t.UserAccount.__table__, 'username', 'root')['password_hash']), True),
        ))
        for role, account in accounts.items():
            def account_check(role=role, account=account):
                user = row(t.UserAccount.__table__, 'user_id', account['user_id'])
                equal(user['username'], account['username'])
                equal(user['identity_type'], account['identity_type'])
                equal(verify_password('123456', user['password_hash']), True)
                assert user['password_hash'].startswith('$argon2'), 'Password must be stored as an Argon2 hash'
                identity = account['identity_type']
                column = identity + '_id'
                equal(user[column], account[column])
                table = {'employee': t.employee, 'customer': t.customer_profile, 'student': t.student_profile}[identity]
                profile = row(table, column, account[column])
                equal(profile['department_id'], account['department_id'])
                if identity == 'employee':
                    equal(profile['position_title'], account['position_title'])
                    equal(profile['role_codes'], account['role_codes'])
                    equal(profile['status'], 'active')
            check('linked account, password and roles: ' + role, account_check)

        for suffix in ('A', 'B'):
            check('department ' + suffix, lambda suffix=suffix: fields_equal(t.org_department, 'department_id', ids['department' + suffix], {
                'department_code': run['run_id'] + '_' + suffix, 'status': 'active',
            }))

        check('qualified customer assigned to consultant', lambda: fields_equal(t.customer_profile, 'customer_id', ids['customer'], {
            'employee_id': accounts['consultant']['employee_id'], 'department_id': ids['departmentA'],
            'status': 'qualified', 'row_version': 5, 'is_archived': False,
        }))
        check('customer followup author and subject', lambda: fields_equal(own.customer_followup, 'followup_id', ids['followup'], {
            'employee_id': accounts['consultant']['employee_id'], 'customer_id': ids['customer'], 'channel': 'phone',
        }))
        check('student linked to registered customer', lambda: fields_equal(t.student_profile, 'student_id', ids['student'], {'customer_id': ids['customer']}))

        for role in ('teacher', 'counselor', 'academic', 'teacherB'):
            expected = {'employee_id': accounts[role]['employee_id'],
                        'student_id': ids['studentB' if role == 'teacherB' else 'student'],
                        'relation_type': 'score_editor' if role == 'academic' else 'class_teacher',
                        'is_primary': role in ('teacher', 'teacherB'), 'status': 'active',
                        'course_scope_code': ids['courseCode'] if role == 'academic' else None}
            check('student service binding: ' + role, lambda role=role, expected=expected: fields_equal(t.student_staff_binding, 'binding_id', ids['binding-' + role], expected))

        check('active local course', lambda: fields_equal(own.enterprise_course, 'course_id', ids['course'], {'course_code': ids['courseCode'], 'status': 'active'}))
        check('student course enrollment', lambda: fields_equal(own.enterprise_student_course, 'enrollment_id', ids['enrollment'], {
            'student_id': ids['student'], 'course_code': ids['courseCode'], 'term_code': '2026-FALL', 'status': 'active',
        }))
        check('corrected score stored by academic employee', lambda: fields_equal(t.student_score, 'score_id', ids['score'], {
            'student_id': ids['student'], 'course_code': ids['courseCode'], 'employee_id': accounts['academic']['employee_id'],
            'score_value': 91, 'max_score': 100, 'status': 'valid', 'row_version': 2,
        }))

        check('rescheduled local exam has no fabricated sync', lambda: fields_equal(t.student_academic_event, 'id', ids['event'], {
            'student_id': ids['student'], 'source_system': 'local', 'event_type': 'exam',
            'event_status': 'active', 'event_version': 2, 'synced_at': None,
        }))

        def reminder_check():
            reminder = fields_equal(t.student_academic_reminder, 'id', ids['reminder'], {
                'student_id': ids['student'], 'academic_event_id': ids['event'], 'lead_minutes': 1440,
                'event_version': 2, 'status': 'pending', 'sent_at': None,
            })
            event = row(t.student_academic_event, 'id', ids['event'])
            equal(reminder['notify_at'], event['due_at'] - timedelta(days=1))
        check('reminder automatically rescheduled to new exam time', reminder_check)
        check('completed application stage has no fabricated sync', lambda: fields_equal(t.student_application_progress, 'id', ids['progress'], {
            'student_id': ids['student'], 'source_system': 'local', 'stage_code': 'document_review',
            'stage_status': 'completed', 'row_version': 2, 'synced_at': None,
        }))
        check('leave approved by bound primary teacher', lambda: fields_equal(t.student_admin_service, 'id', ids['leave'], {
            'student_id': ids['student'], 'reviewer_id': accounts['teacher']['employee_id'],
            'apply_type': 'leave', 'approval_status': 'approved', 'row_version': 2,
        }))
        check('second leave withdrawn by student', lambda: fields_equal(t.student_admin_service, 'id', ids['withdrawnLeave'], {
            'student_id': ids['student'], 'approval_status': 'cancelled', 'row_version': 2,
        }))
        check('ticket reopened, resolved, student-confirmed and rated', lambda: fields_equal(t.service_ticket, 'ticket_id', ids['ticket'], {
            'student_id': ids['student'], 'employee_id': accounts['teacher']['employee_id'],
            'handling_department_id': ids['departmentA'], 'status': 'closed',
            'reopen_count': 1, 'satisfaction_score': 5, 'row_version': 9,
        }))

        def ticket_history_check():
            records = db.execute(select(t.service_ticket_record).where(t.service_ticket_record.c.ticket_id == ids['ticket']).order_by(t.service_ticket_record.c.ticket_record_id)).mappings().all()
            snapshot['ticket_history'] = [{k: r[k] for k in ('ticket_record_id', 'record_type', 'employee_id', 'student_id', 'to_status', 'cycle_no', 'visibility')} for r in records]
            assert len(records) >= 9, f'Incomplete history: {len(records)} records'
            closed = [r for r in records if r['to_status'] == 'closed']
            assert closed, 'Missing closure record'
            equal(closed[-1]['student_id'], ids['student'])
            assert any(r['to_status'] == 'reopened' and r['student_id'] == ids['student'] for r in records)
            assert any(r['employee_id'] == accounts['manager']['employee_id'] for r in records)
            assert any(r['employee_id'] == accounts['teacher']['employee_id'] for r in records)
            ticket = row(t.service_ticket, 'ticket_id', ids['ticket'])
            assert ticket['closed_at'] >= ticket['resolved_at'] >= ticket['first_response_at']
        check('ticket history actors and final timestamps', ticket_history_check)

        for key, role, department in [('daily', 'employee', 'departmentA'), ('dailyB', 'consultantB', 'departmentB')]:
            check('daily report author and department: ' + role, lambda key=key, role=role, department=department: fields_equal(own.employee_daily_report, 'daily_report_id', ids[key], {
                'employee_id': accounts[role]['employee_id'], 'department_id_at_submit': ids[department], 'status': 'submitted',
            }))
        check('published knowledge department scope and index', lambda: fields_equal(own.knowledge_entry, 'knowledge_id', ids['knowledge'], {
            'status': 'published', 'access_department_id': ids['departmentA'], 'index_status': 'ready', 'row_version': 2,
        }))

        def notification_check():
            notice = fields_equal(t.business_notification, 'notification_id', ids['notification'], {'student_id': ids['student'], 'delivery_status': 'sent'})
            assert notice['sent_at'] is not None and notice['read_at'] is not None
            assert notice['read_at'] >= notice['sent_at']
        check('real notification delivered and marked read', notification_check)

        def audit_check():
            all_calls = run['calls'] + (refresh['calls'] if refresh else [])
            calls = [c for c in all_calls if c.get('request_key') and c['code'] == 0 and c['operation'].split()[0] != 'GET' and '/report/' not in c['operation']]
            logs = db.execute(select(t.operation_log).where(t.operation_log.c.request_key.in_([c['request_key'] for c in calls]))).mappings().all()
            by_key = {r['request_key']: r for r in logs}
            snapshot['audit_counts'] = {'successful_ui_writes': len(calls), 'matching_audit_records': len(logs)}
            for call in calls:
                assert call['request_key'] in by_key, 'Missing audit: ' + call['operation']
                log = by_key[call['request_key']]
                equal(log['operation_status'], 'succeeded')
                if call['role'] != 'root':
                    account = accounts[call['role']]
                    actor_field = account['identity_type'] + '_id'
                    equal(log[actor_field], account[actor_field])
            snapshot['audit_records'] = [{k: r[k] for k in ('operation_log_id', 'action_code', 'employee_id', 'student_id', 'service_code', 'operation_status')} for r in logs]
        check('successful frontend writes have matching audit actors', audit_check)
        check('browser scenarios have no failures or runtime errors', lambda: (equal(run['summary']['failed'], 0), equal(run['errors'], [])))
        if refresh:
            check('consecutive frontend edits and final daily report version', lambda: (
                equal(refresh['status'], 'passed'),
                equal(refresh['final_version'], refresh['initial_version'] + 2),
                fields_equal(own.employee_daily_report, 'daily_report_id', ids['daily'], {'row_version': refresh['final_version']}),
            ))
        db.rollback()

    summary = {status: sum(c['status'] == status for c in checks) for status in ('passed', 'failed')}
    result = {'run_id': run['run_id'], 'verified_at': datetime.now(timezone.utc).isoformat(),
              'database': 'education_agent', 'mode': 'START TRANSACTION READ ONLY', 'summary': summary,
              'checks': checks, 'snapshot': snapshot}
    (directory / 'database-verification.json').write_text(json.dumps(result, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return 1 if summary['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
