"""飞书文档 API 封装"""

from api.auth import FeishuAuth


class DocumentsAPI:
    """文档相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def list_files(self, folder_token: str = "", page_token: str = "", order_by: str = "EditedTime") -> dict:
        """
        获取云文档列表

        :param folder_token: 文件夹 token，空表示根目录
        :param page_token: 分页 token
        :param order_by: 排序方式 (EditedTime / CreatedTime)
        :return: API 响应数据
        """
        params = {
            "page_size": 50,
            "order_by": order_by,
        }
        if folder_token:
            params["folder_token"] = folder_token
        if page_token:
            params["page_token"] = page_token

        return self.auth.request("GET", "/drive/v1/files", params=params)

    def get_all_files(self, folder_token: str = "") -> list[dict]:
        """获取所有文件（自动分页）"""
        all_files = []
        page_token = ""

        while True:
            data = self.list_files(folder_token, page_token)
            items = data.get("data", {}).get("files", [])
            all_files.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("next_page_token", "")

        return all_files

    def get_document_content(self, document_id: str, page_token: str = "") -> dict:
        """
        获取文档内容（docx 格式）

        :param document_id: 文档 ID
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token

        return self.auth.request(
            "GET",
            f"/docx/v1/documents/{document_id}/blocks",
            params=params,
        )

    def get_document_meta(self, document_id: str) -> dict:
        """
        获取文档元信息

        :param document_id: 文档 ID
        :return: API 响应数据
        """
        return self.auth.request("GET", f"/docx/v1/documents/{document_id}")

    def get_document_raw_content(self, document_id: str) -> dict:
        """
        获取文档纯文本内容

        :param document_id: 文档 ID
        :return: API 响应数据
        """
        return self.auth.request("GET", f"/docx/v1/documents/{document_id}/raw_content")

    def search_docs(self, query: str, docs_token: str = "", page_token: str = "") -> dict:
        """
        搜索文档

        :param query: 搜索关键词
        :param docs_token: 文档 token 过滤
        :param page_token: 分页 token
        :return: API 响应数据
        """
        payload = {
            "search_key": query,
            "count": 20,
            "offset": 0,
        }
        if docs_token:
            payload["docs_token"] = docs_token

        return self.auth.request("POST", "/suite/docs-api/search/object", json=payload)

    def get_file_meta(self, file_token: str, file_type: str) -> dict:
        """
        获取文件元信息

        :param file_token: 文件 token
        :param file_type: 文件类型 (doc, sheet, bitable, docx, folder)
        :return: API 响应数据
        """
        return self.auth.request(
            "GET",
            f"/drive/v1/metas",
            json={
                "request": [
                    {
                        "doc_token": file_token,
                        "doc_type": file_type,
                    }
                ]
            },
        )
