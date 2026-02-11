"""飞书多维表格 (Bitable) API 封装"""

from api.auth import FeishuAuth


class BitableAPI:
    """多维表格相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    # ── 多维表格管理 ──────────────────────────

    def create_bitable(self, name: str, folder_token: str = "") -> dict:
        """
        创建多维表格

        :param name: 多维表格名称
        :param folder_token: 目标文件夹 token，空表示根目录
        :return: API 响应数据（含 app_token）
        """
        payload = {"name": name}
        if folder_token:
            payload["folder_token"] = folder_token
        return self.auth.request("POST", "/bitable/v1/apps", json=payload)

    def get_bitable_meta(self, app_token: str) -> dict:
        """
        获取多维表格元信息

        :param app_token: 多维表格 token
        :return: API 响应数据
        """
        return self.auth.request("GET", f"/bitable/v1/apps/{app_token}")

    # ── 数据表管理 ──────────────────────────

    def list_tables(self, app_token: str, page_token: str = "") -> dict:
        """
        获取所有数据表列表

        :param app_token: 多维表格 token
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        return self.auth.request(
            "GET", f"/bitable/v1/apps/{app_token}/tables", params=params
        )

    def create_table(self, app_token: str, name: str, fields: list[dict] = None) -> dict:
        """
        创建数据表

        :param app_token: 多维表格 token
        :param name: 数据表名称
        :param fields: 字段定义列表，如 [{"field_name": "姓名", "type": 1}]
                       type: 1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选, 11=人员, 13=电话, 15=链接, 17=附件, 18=关联, 20=公式, 21=双向关联, 22=地理位置, 23=群组, 1001=创建时间, 1002=修改时间, 1003=创建人, 1004=修改人
        :return: API 响应数据
        """
        table_def = {"name": name}
        if fields:
            table_def["fields"] = fields

        payload = {"table": table_def}
        return self.auth.request(
            "POST", f"/bitable/v1/apps/{app_token}/tables", json=payload
        )

    def delete_table(self, app_token: str, table_id: str) -> dict:
        """
        删除数据表

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :return: API 响应数据
        """
        return self.auth.request(
            "DELETE", f"/bitable/v1/apps/{app_token}/tables/{table_id}"
        )

    # ── 字段管理 ──────────────────────────

    def list_fields(self, app_token: str, table_id: str, page_token: str = "") -> dict:
        """
        获取字段列表

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        return self.auth.request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            params=params,
        )

    def create_field(self, app_token: str, table_id: str, field_name: str, field_type: int) -> dict:
        """
        创建字段

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param field_name: 字段名称
        :param field_type: 字段类型（1=文本, 2=数字, 3=单选, 等）
        :return: API 响应数据
        """
        payload = {"field_name": field_name, "type": field_type}
        return self.auth.request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            json=payload,
        )

    # ── 记录管理 ──────────────────────────

    def list_records(
        self, app_token: str, table_id: str,
        page_size: int = 100, page_token: str = "",
        filter_str: str = "", sort_str: str = "",
    ) -> dict:
        """
        获取记录列表

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param page_size: 每页数量（最大 500）
        :param page_token: 分页 token
        :param filter_str: 过滤条件
        :param sort_str: 排序条件
        :return: API 响应数据
        """
        params = {"page_size": min(page_size, 500)}
        if page_token:
            params["page_token"] = page_token
        if filter_str:
            params["filter"] = filter_str
        if sort_str:
            params["sort"] = sort_str
        return self.auth.request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            params=params,
        )

    def get_all_records(self, app_token: str, table_id: str, max_count: int = 5000) -> list[dict]:
        """
        获取所有记录（自动分页）

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param max_count: 最大获取条数
        :return: 记录列表
        """
        all_records = []
        page_token = ""

        while len(all_records) < max_count:
            data = self.list_records(app_token, table_id, page_size=500, page_token=page_token)
            items = data.get("data", {}).get("items", [])
            all_records.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return all_records[:max_count]

    def get_record(self, app_token: str, table_id: str, record_id: str) -> dict:
        """
        获取单条记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param record_id: 记录 ID
        :return: API 响应数据
        """
        return self.auth.request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        )

    def create_record(self, app_token: str, table_id: str, fields: dict) -> dict:
        """
        创建单条记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param fields: 字段键值对，如 {"姓名": "张三", "年龄": 25}
        :return: API 响应数据
        """
        payload = {"fields": fields}
        return self.auth.request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json=payload,
        )

    def batch_create_records(self, app_token: str, table_id: str, records: list[dict]) -> dict:
        """
        批量创建记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param records: 记录列表，每条为 {"fields": {"字段名": "值"}}
        :return: API 响应数据
        """
        payload = {"records": records}
        return self.auth.request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            json=payload,
        )

    def update_record(self, app_token: str, table_id: str, record_id: str, fields: dict) -> dict:
        """
        更新单条记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param record_id: 记录 ID
        :param fields: 要更新的字段键值对
        :return: API 响应数据
        """
        payload = {"fields": fields}
        return self.auth.request(
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json=payload,
        )

    def batch_update_records(self, app_token: str, table_id: str, records: list[dict]) -> dict:
        """
        批量更新记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param records: 记录列表，每条为 {"record_id": "xxx", "fields": {...}}
        :return: API 响应数据
        """
        payload = {"records": records}
        return self.auth.request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            json=payload,
        )

    def delete_record(self, app_token: str, table_id: str, record_id: str) -> dict:
        """
        删除单条记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param record_id: 记录 ID
        :return: API 响应数据
        """
        return self.auth.request(
            "DELETE",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        )

    def batch_delete_records(self, app_token: str, table_id: str, record_ids: list[str]) -> dict:
        """
        批量删除记录

        :param app_token: 多维表格 token
        :param table_id: 数据表 ID
        :param record_ids: 记录 ID 列表
        :return: API 响应数据
        """
        payload = {"records": record_ids}
        return self.auth.request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            json=payload,
        )
