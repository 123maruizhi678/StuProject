"""公共装配、唯一映射、源DDL列与前端资源检查。"""
from pathlib import Path
import re
import unittest
from fastapi.testclient import TestClient
from app.database import Base
from app.models import common

ROOT=Path(__file__).resolve().parents[2]


class CommonContractTests(unittest.TestCase):
    def test_only_common_business_routes_are_mounted(self):
        from app.main import app
        paths=app.openapi()["paths"]
        expected={"/api/v1/auth/login","/api/v1/auth/public-access","/api/v1/auth/me/access","/health"}
        self.assertEqual(set(paths),expected)
        operation_ids=[v["operationId"] for methods in paths.values() for v in methods.values() if isinstance(v,dict) and "operationId" in v]
        self.assertEqual(len(operation_ids),len(set(operation_ids)))

    def test_canonical_identity_tables_match_ddl_columns_and_nullability(self):
        sql=(ROOT/"开发文档/操作文档_数据库建表语句.sql").read_text(encoding="utf-8-sig")
        for name in common.__all__:
            item=getattr(common,name)
            table=item.__table__ if name=="UserAccount" else item
            self.assertIs(table.metadata,Base.metadata)
            block=re.search(r"CREATE TABLE "+chr(96)+table.name+chr(96)+r" \(.*?\) ENGINE=.*?;",sql,re.S)
            self.assertIsNotNone(block,table.name)
            columns=re.findall(r"^  "+chr(96)+r"(\w+)"+chr(96)+r" (.*)$",block.group(),re.M)
            expected={name for name,_ in columns}
            if table.name=="operation_log":
                expected.add("actor_account_id")
            self.assertEqual(set(table.c.keys()),expected,table.name)
            for col_name,definition in columns:
                self.assertEqual(table.c[col_name].nullable,"NOT NULL" not in definition,table.name+"."+col_name)

    def test_frontend_and_static_resources_are_served(self):
        from app.main import app
        with TestClient(app) as client:
            for path in ["/","/login","/account","/static/js/common/api.js","/static/js/common/app.js","/static/css/common/style.css"]:
                self.assertEqual(client.get(path).status_code,200,path)
            for file in ["frontend/index.html","frontend/common/login.html"]:
                html=(ROOT/file).read_text(encoding="utf-8")
                for asset in re.findall(r'(?:src|href)="(/static/[^"]+)',html):
                    self.assertTrue((ROOT/"frontend"/asset.removeprefix("/static/")).is_file(),asset)
