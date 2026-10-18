"""客户资料文件读取。保留工作表及原始行号，不合并不同客户。"""
import csv
import io
from zipfile import ZipFile
from xml.etree import ElementTree

from app.services.customer.errors import BadRequestError


def decode_text(data):
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
        if encoding == 'utf-16' and not data.startswith((b'\xff\xfe', b'\xfe\xff')):
            continue
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BadRequestError('文本编码无法识别，请转换为 UTF-8 后重试')


def check_archive(data):
    with ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
            raise BadRequestError('文件解压内容超过 100 MB，请拆分文件')


def read_docx(data, labels=()):
    try:
        check_archive(data)
        with ZipFile(io.BytesIO(data)) as archive:
            root = ElementTree.fromstring(archive.read('word/document.xml'))
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        lines = []
        def text_of(node):
            return ''.join(t.text or '' for t in node.iter(ns + 't')).strip()
        def visit(node):
            if node.tag == ns + 'tr':
                cells = [text_of(cell) for cell in node.findall(ns + 'tc')]
                index = 0
                while index < len(cells):
                    key = cells[index].strip(' :：')
                    if key in labels and index + 1 < len(cells):
                        lines.append(key + '：' + cells[index + 1])
                        index += 2
                    else:
                        lines.append(cells[index])
                        index += 1
            elif node.tag == ns + 'p':
                lines.append(text_of(node))
            else:
                for child in node:
                    visit(child)
        visit(root)
        text = '\n'.join(lines).strip()
    except BadRequestError:
        raise
    except Exception as exc:
        raise BadRequestError('Word 文件无法读取，请确认是未加密的 DOCX 文件；旧版 DOC 请另存为 DOCX') from exc
    if not text:
        raise BadRequestError('Word 文件没有可提取的文字，请补充客户文字资料')
    return text


def read_tables(data, suffix, aliases, fields, max_rows):
    book = None
    warnings = []
    try:
        if suffix in ('.csv', '.tsv'):
            delimiter = '\t' if suffix == '.tsv' else ','
            sheets = [('', csv.reader(io.StringIO(decode_text(data)), delimiter=delimiter))]
        elif suffix == '.xls':
            try:
                import xlrd
            except ImportError as exc:
                raise BadRequestError('旧版 XLS 读取组件未安装，请安装客户模块 requirements 或另存为 XLSX') from exc
            book = xlrd.open_workbook(file_contents=data, on_demand=True)
            if book.nsheets > 30:
                raise BadRequestError('工作簿超过 30 个工作表，请拆分文件')
            def xls_rows(sheet):
                for index in range(sheet.nrows):
                    yield sheet.row_values(index)
            sheets = [(s.name, xls_rows(s)) for s in book.sheets()]
        else:
            import openpyxl
            check_archive(data)
            book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            if len(book.worksheets) > 30:
                raise BadRequestError('工作簿超过 30 个工作表，请拆分文件')
            sheets = [(s.title, s.iter_rows(values_only=True)) for s in book.worksheets]
        records = []
        for name, rows in sheets:
            iterator = iter(rows)
            # 允许表头前有少量空白行，仍保留真实行号。
            first = None
            for header_row, candidate in enumerate(iterator, 1):
                if header_row > 10000:
                    raise BadRequestError('表格扫描范围超过 10000 行，请移除多余空行')
                if any(v is not None and str(v).strip() for v in candidate):
                    first = candidate
                    break
            if first is None:
                continue
            if len(first) > 100:
                raise BadRequestError('表格超过 100 列，请保留客户资料列后重试')
            headers = [str(v).strip() if v is not None else '' for v in first]
            mapped = [aliases.get(h, h.lower() if h.lower() in fields else None) for h in headers]
            recognized = [h for h in mapped if h]
            if not recognized:
                warnings.append('未识别客户表头，已跳过工作表：' + (name or '当前表格'))
                continue
            if len(set(recognized)) != len(recognized):
                raise BadRequestError('多个表头映射到同一个客户字段，请删除重复列：' + (name or '当前表格'))
            for index, row in enumerate(iterator, header_row + 1):
                if index > 10000:
                    raise BadRequestError('表格扫描范围超过 10000 行，请移除多余空行')
                if not any(v is not None and str(v).strip() for v in row):
                    continue
                raw = {key: row[i] for i, key in enumerate(mapped)
                       if key and i < len(row) and row[i] is not None and str(row[i]).strip()}
                records.append((name, index, raw))
                if len(records) > max_rows:
                    raise BadRequestError('单次最多支持 200 位客户（所有工作表合计），请拆分表格')
        if not records:
            raise BadRequestError('表格为空、没有客户记录或未识别到客户字段表头，请使用客户资料模板')
        return records, warnings
    except BadRequestError:
        raise
    except Exception as exc:
        raise BadRequestError('表格无法读取，请确认文件格式与扩展名一致，且文件未加密或损坏') from exc
    finally:
        if book is not None:
            if suffix == '.xls':
                book.release_resources()
            else:
                book.close()
