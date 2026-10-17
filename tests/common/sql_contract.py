"""Read shared column contracts from the SQL baseline and explicit increments."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPE = r"(?:BIGINT|INTEGER|INT|TINYINT|VARCHAR|CHAR|TEXT|JSON|DATETIME|DATE|DECIMAL|BOOLEAN|VARBINARY)\b"


def columns_for(table):
    source = (ROOT / "scripts/sql/all.sql").read_text(encoding="utf-8-sig")
    create = re.search(r"CREATE TABLE `?" + table + r"`?\s*\(.*?;", source, re.S)
    if create is None:
        raise AssertionError(f"Missing baseline DDL: {table}")
    columns = {}
    for line in create.group().splitlines()[1:]:
        match = re.match(r"\s*`?(\w+)`?\s+(" + TYPE + r")(.*)", line)
        if match:
            name, kind, definition = match.groups()
            columns[name] = (kind, "NOT NULL" not in definition)
    increment = (ROOT / "scripts/sql/enterprise/002_shared_runtime_fields.sql").read_text(encoding="utf-8")
    for statement in re.findall(r"ALTER TABLE `?" + table + r"`?\s+(.*?);", source + "\n" + increment, re.S):
        for match in re.finditer(r"(?:ADD|MODIFY)\s+COLUMN\s+`?(\w+)`?\s+(" + TYPE + r")(.*?)(?=,\s*(?:ADD|MODIFY|DROP)\s|$)", statement, re.S):
            name, kind, definition = match.groups()
            columns[name] = (kind, "NOT NULL" not in definition)
            after = re.search(r"\bAFTER\s+`?(\w+)`?", definition)
            if after:
                value = columns.pop(name)
                ordered = {}
                for other, contract in columns.items():
                    ordered[other] = contract
                    if other == after.group(1):
                        ordered[name] = value
                columns = ordered
    return columns
