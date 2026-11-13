"""
班次查询工具 - LangChain Tool
"""
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional
from app.services.ticket_service import TicketService
from datetime import datetime
import json


class TicketSearchInput(BaseModel):
    """班次查询输入参数"""
    departure: str = Field(description="出发地城市名称，如：北京、上海")
    destination: str = Field(description="目的地城市名称，如：上海、广州")
    date: Optional[str] = Field(default=None, description="出发日期，格式：YYYY-MM-DD，如：2026-02-15")


class TicketSearchTool(BaseTool):
    """班次查询工具"""
    name: str = "ticket_search"
    description: str = """查询班次信息的工具。
    
    使用场景：
    - 用户询问班次、车票、车次信息
    - 用户想要查询出行计划
    - 用户提到出发地和目的地
    
    输入参数：
    - departure: 出发地（必填）
    - destination: 目的地（必填）
    - date: 出发日期（可选，默认今天）
    
    示例：
    - "查询北京到上海的班次" → departure="北京", destination="上海"
    - "明天从成都到重庆" → departure="成都", destination="重庆", date="2026-02-12"
    """
    args_schema: type[BaseModel] = TicketSearchInput
    
    # 使用 PrivateAttr 声明私有属性
    _ticket_service: Optional[TicketService] = PrivateAttr(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化服务
        self._ticket_service = TicketService()
    
    def _run(
        self,
        departure: str,
        destination: str,
        date: Optional[str] = None
    ) -> str:
        """执行班次查询"""
        try:
            # 确保服务已初始化
            if self._ticket_service is None:
                self._ticket_service = TicketService()
            
            # 验证参数
            if not departure or not destination:
                # json.dumps() 将 Python 字典转换为 JSON 字符串，ensure_ascii=False 保证中文不被转义
                # json.loads() 将 JSON 字符串转换为 Python 字典
                return json.dumps({
                    "success": False,
                    "error": "缺少出发地或目的地",
                    "need_info": ["departure", "destination"]
                }, ensure_ascii=False)
            
            if departure == destination:
                return json.dumps({
                    "success": False,
                    "error": "出发地和目的地不能相同"
                }, ensure_ascii=False)
            
            # 处理日期
            if not date:  # 缺少日期用当前日期
                date = datetime.now().strftime("%Y-%m-%d")
            
            # 查询班次
            tickets = self._ticket_service.search_tickets(
                departure=departure,
                destination=destination,
                date=date
            )
            
            if not tickets:
                return json.dumps({
                    "success": True,
                    "count": 0,
                    "message": f"未找到 {departure} 到 {destination} 的班次"
                }, ensure_ascii=False)
            
            # 格式化结果（只返回前6个）
            formatted_tickets = []
            for i, ticket in enumerate(tickets[:6], 1):
                formatted_tickets.append({
                    "序号": i,
                    "发车时间": ticket.get('departure_time', 'N/A'),
                    "到达时间": ticket.get('arrival_time', 'N/A'),
                    "车型": ticket.get('vehicle_type', '未知'),
                    "票价": f"{ticket.get('price', 'N/A')}元",
                    "余票": ticket.get('seats_available', '充足')
                })
            
            return json.dumps({
                "success": True,
                "count": len(tickets),
                "displayed": len(formatted_tickets),
                "query": {
                    "departure": departure,
                    "destination": destination,
                    "date": date
                },
                "tickets": formatted_tickets
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            import traceback
            print(f"[TicketSearchTool] 错误: {e}")
            print(traceback.format_exc())
            return json.dumps({
                "success": False,
                "error": f"查询失败: {str(e)}"
            }, ensure_ascii=False)
    
    async def _arun(
        self,
        departure: str,
        destination: str,
        date: Optional[str] = None
    ) -> str:
        """异步执行（当前使用同步实现）"""
        return self._run(departure, destination, date)
