def test_minimal_dependencies():
    from app.services.student.student_leave_service import StudentLeaveService
    from app.services.student.student_ticket_service import StudentTicketService
    from app.repositories.student.student_schema import require_student_schema

def test_direct_submit(unit):
    from app.services.student.student_service import StudentService
    from app.schemas.student.student import LeaveInput
    from app.repositories.student.student_schema import check_student_schema
    with unit.sessions() as db:
        assert check_student_schema(db.connection(),'leave')['issues']==[]
        StudentService(db).submit_leave(unit.state.actor,'debug-0001',LeaveInput(leave_content='测试',leave_start_at='2027-01-20T09:00:00+08:00',leave_end_at='2027-01-20T18:00:00+08:00'))

def test_direct_ticket(unit):
    from app.services.student.student_service import StudentService
    from app.schemas.student.student import TicketInput
    with unit.sessions() as db:
        StudentService(db).submit_ticket(unit.state.actor,'debug-ticket-0001',TicketInput(content='测试',ticket_type='suggestion'))
