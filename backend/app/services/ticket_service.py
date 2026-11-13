"""
班次查询服务
"""
from datetime import datetime, timedelta
import requests


class TicketService:
    """班次查询服务"""

    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or "http://localhost:9001"

    # 获取模拟数据，实际要改为真实查票，那就要对接第三方的查票接口，或者自己搭建一个查票服务【12306啥的】
    def search_tickets(self, departure: str, destination: str, date: str = None):
        """查询班次"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        return self._get_mock_data(departure, destination, date)

        # try:
        #     # TODO: 替换为实际的API调用
        #     response = requests.get(
        #         f"{self.api_base_url}/tickets",
        #         params={
        #             "from": departure,
        #             "to": destination,
        #             "date": date
        #         },
        #         timeout=10
        #     )
        #     response.raise_for_status()
        #
        #     data = response.json()
        #     return data.get("tickets", [])
        #
        # except Exception as e:
        #     print(f"查询班次失败: {e}")
        #     # 返回模拟数据用于开发测试
        #     return self._get_mock_data(departure, destination, date)

    # 模拟数据，在接入第三方服务后，可作为兜底的 mock 数据
    def _get_mock_data(self, departure: str, destination: str, date: str):
        """模拟数据（开发用）"""
        return [
            {
                "departure_time": "08:00",
                "arrival_time": "13:30",
                "duration": "5h30m",
                "vehicle_type": "高铁",
                "price": 553,
                "seats_available": 99
            },
            {
                "departure_time": "10:30",
                "arrival_time": "16:00",
                "duration": "5h30m",
                "vehicle_type": "动车",
                "price": 443,
                "seats_available": 15
            },
            {
                "departure_time": "14:00",
                "arrival_time": "20:30",
                "duration": "6h30m",
                "vehicle_type": "大巴",
                "price": 150,
                "seats_available": 20
            }
        ]