"""飞书表格 (Spreadsheet) API 封装"""

from api.auth import FeishuAuth


class SheetsAPI:
    """表格相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    # ── 表格管理 ──────────────────────────

    def create_spreadsheet(self, title: str, folder_token: str = "") -> dict:
        """
        创建表格

        :param title: 表格标题
        :param folder_token: 目标文件夹 token，空表示根目录
        :return: API 响应数据（含 spreadsheet_token）
        """
        payload = {"title": title}
        if folder_token:
            payload["folder_token"] = folder_token
        return self.auth.request("POST", "/sheets/v3/spreadsheets", json=payload)

    def get_spreadsheet_meta(self, spreadsheet_token: str) -> dict:
        """
        获取表格元信息

        :param spreadsheet_token: 表格 token
        :return: API 响应数据
        """
        return self.auth.request(
            "GET", f"/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo"
        )

    # ── 工作表管理 ──────────────────────────

    def list_sheets(self, spreadsheet_token: str) -> dict:
        """
        获取所有工作表列表

        :param spreadsheet_token: 表格 token
        :return: API 响应数据（含 sheets 列表）
        """
        return self.auth.request(
            "GET", f"/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query"
        )

    def add_sheet(self, spreadsheet_token: str, title: str) -> dict:
        """
        新增工作表

        :param spreadsheet_token: 表格 token
        :param title: 工作表标题
        :return: API 响应数据
        """
        payload = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {"title": title}
                    }
                }
            ]
        }
        return self.auth.request(
            "POST",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update",
            json=payload,
        )

    # ── 数据读写 ──────────────────────────

    def read_data(self, spreadsheet_token: str, range_str: str) -> dict:
        """
        读取工作表数据

        :param spreadsheet_token: 表格 token
        :param range_str: 读取范围，如 "Sheet1!A1:D5" 或 "sheetId!A1:D5"
        :return: API 响应数据
        """
        return self.auth.request(
            "GET",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values/{range_str}",
            params={"valueRenderOption": "ToString"},
        )

    def write_data(self, spreadsheet_token: str, range_str: str, values: list) -> dict:
        """
        写入数据到指定范围

        :param spreadsheet_token: 表格 token
        :param range_str: 写入范围，如 "Sheet1!A1:D5"
        :param values: 二维数组，如 [["A1","B1"],["A2","B2"]]
        :return: API 响应数据
        """
        payload = {
            "valueRange": {
                "range": range_str,
                "values": values,
            }
        }
        return self.auth.request(
            "PUT",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            json=payload,
        )

    def append_data(self, spreadsheet_token: str, range_str: str, values: list) -> dict:
        """
        追加数据到工作表（自动在已有数据后面追加）

        :param spreadsheet_token: 表格 token
        :param range_str: 范围，如 "Sheet1!A:D"
        :param values: 二维数组
        :return: API 响应数据
        """
        payload = {
            "valueRange": {
                "range": range_str,
                "values": values,
            }
        }
        return self.auth.request(
            "POST",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values_append",
            json=payload,
            params={"insertDataOption": "INSERT_ROWS"},
        )

    def batch_read(self, spreadsheet_token: str, ranges: list[str]) -> dict:
        """
        批量读取多个范围的数据

        :param spreadsheet_token: 表格 token
        :param ranges: 范围列表，如 ["Sheet1!A1:D5", "Sheet2!A1:C3"]
        :return: API 响应数据
        """
        params = {
            "ranges": ",".join(ranges),
            "valueRenderOption": "ToString",
        }
        return self.auth.request(
            "GET",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_get",
            params=params,
        )

    def batch_write(self, spreadsheet_token: str, value_ranges: list[dict]) -> dict:
        """
        批量写入多个范围的数据

        :param spreadsheet_token: 表格 token
        :param value_ranges: 写入数据列表，每个元素 {"range": "...", "values": [[...]]}
        :return: API 响应数据
        """
        payload = {"valueRanges": value_ranges}
        return self.auth.request(
            "POST",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
            json=payload,
        )
