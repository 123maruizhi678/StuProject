"""操作文档054、057、058的版本化默认策略，所有时点均为UTC。"""
from datetime import timedelta
from app.core.common.response import BusinessException

POLICY_VERSION = 'student-20261017-v1'
SCAN_SECONDS = 300
ROUND_SECONDS = 86400
NOTIFICATION_RETRY_MINUTES = (1, 5, 15, 60, 240)
TICKET_HOURS = {
    ('complaint','normal'):(24,72),
    ('complaint','high'):(4,24),
    ('suggestion','normal'):(48,120),
    ('suggestion','high'):(24,72),
}


def ticket_cycle(ticket_type, priority, now, cycle_no):
    if (ticket_type,priority) not in TICKET_HOURS:
        raise BusinessException('工单时限策略尚未配置',503)
    response,resolution=TICKET_HOURS[ticket_type,priority]
    return {'policy_version':POLICY_VERSION,'cycle_no':cycle_no,
            'started_at':now.isoformat(timespec='microseconds')+'Z',
            'response_hours':response,'resolution_hours':resolution,
            'response_due_at':(now+timedelta(hours=response)).isoformat(timespec='microseconds')+'Z',
            'resolution_due_at':(now+timedelta(hours=resolution)).isoformat(timespec='microseconds')+'Z'}
