"""固定工单服务的可选摘要适配；不部署第二个应用。"""
class StudentTicketDifyError(Exception):
    def __init__(self,code='summary_unavailable'):
        self.code=code
        super().__init__(code)
def get_ticket_workflow():
    from .student_assistant_dify import TicketWorkflowAdapter
    return TicketWorkflowAdapter()
