"""旧最小单元异常兼容；模型能力转到唯一学生应用。"""
class StudentLeaveDifyError(Exception):
    def __init__(self,status=503,message='学生摘要服务不可用'):
        self.status,self.message=status,message
        super().__init__(message)
def get_leave_workflow():
    from .student_assistant_dify import LeaveWorkflowAdapter
    return LeaveWorkflowAdapter()
