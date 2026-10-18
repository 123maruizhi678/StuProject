"""多格式解析单元测试（文件类型 / 表头映射 / 白名单）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.customer.errors import BadRequestError
from app.services.customer import parser as p


def test_source_type_from_filename():
    assert p.source_type_from_filename("a.PDF") == "pdf"
    assert p.source_type_from_filename("b.xlsx") == "excel"
    assert p.source_type_from_filename("c.csv") == "excel"
    assert p.source_type_from_filename("d.txt") == "text"
    assert p.source_type_from_filename("e.doc") is None


def test_assert_allowed_file():
    p.assert_allowed_file("a.pdf")
    try:
        p.assert_allowed_file("a.exe")
        assert False, "应抛出 BadRequestError"
    except BadRequestError:
        pass


def test_map_to_info_fields_whitelist():
    out = p.map_to_info_fields({"full_name": "张三", "phone": "13800138000", "evil": "x"})
    assert out == {"full_name": "张三", "phone": "13800138000"}


def test_read_csv_records(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("姓名,年龄,学历\n张三,35,硕士\n李四,40,博士\n", encoding="utf-8")
    recs = p.read_excel_records(str(f))
    assert recs == [
        {"full_name": "张三", "age": "35", "education_level": "硕士"},
        {"full_name": "李四", "age": "40", "education_level": "博士"},
    ]


def test_phone_normalize():
    from app.core.common.security import normalize_phone

    assert normalize_phone("13800138000") == "13800138000"
    assert normalize_phone("+86 138-0013-8000") == "13800138000"
    assert normalize_phone("123") == ""
