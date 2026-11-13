"""
__init__.py，包的标识符，这个目录是一个Python包；里面的代码在这个包被导入时会自动执行【初始化】；
__pycache__：Python自动生成的目录，缓存编译后的字节码文件，提升程序启动速度；【不需要每次都重新编译】
================================
FastAPI 应用的创建
应用的生命周期函数
HTPP 和 WebSocket 路由注册
对 HTTP 请求配置 CORS、GZip 中间件
================================
【同步在阻塞时，不会让出线程；异步在阻塞时，会让出线程，让线程做其他事，阻塞结束之后，再占用线程；】
异步函数定义：在 def 前加上 async 关键字，不加默认是同步函数
在异步函数中，可以用 await 关键字调用异步函数，可以直接调用同步函数
在同步函数中，可以直接调用同步函数，但不能用 await 关键字调用异步函数，需要使用 asyncio.run() 或者 asyncio.create_task() 来运行异步函数

async def a():
    await b()        # ✅ b 是 async def
    c()              # ✅ c 是普通 def，直接调用
    await c()        # ❌ 普通函数不能 await，会报错

    
import asyncio
async def fetch_data():  # 异步函数
    await asyncio.sleep(1)
    return "data"
def main():  # 同步函数
    result = await fetch_data()   # ❌ SyntaxError
    result = asyncio.run(fetch_data())   # ✅ 协程
    print(result)
================================

"""



"""
FastAPI 应用入口
"""
import sys
import os
import logging
from contextlib import asynccontextmanager

# 添加父目录到路径，支持直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.routes import router as chat_router, warmup_workflow
from app.api.websocket import websocket_endpoint
from app.config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



"""
FastAPI 应用的生命周期管理函数，通过@asynccontextmanager装饰器定义，管理应用启动和关闭时的操作。
通过 yield 分隔；
yield 之前的代码在应用启动时执行【初始化、预热、连接池、日志】，yield 之后的代码在应用关闭时执行【资源释放、关闭连接、日志】。
yield 本身把控制权交还给 FastAPI，应用正式对外服务，接收请求和响应。
"""
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    logger.info("旅行规划 Agent API 启动中...")
    logger.info(f"API 文档: http://{settings.API_HOST}:{settings.API_PORT}/docs")

    # 预热工作流（避免首次请求编译延迟）【提前创建并编译LangGraph工作流】
    try:
        warmup_workflow()
        logger.info("工作流预热完成")
    except Exception as e:
        logger.error(f"工作流预热失败: {e}", exc_info=True)

    logger.info("旅行规划 Agent API 启动成功")
    yield
    # 关闭事件
    logger.info("旅行规划 Agent API 关闭")


"""
创建了一个 FastAPI 应用 app
给 HTTP 请求配置了 CORS 中间件，允许跨域请求、允许携带凭证等    add_middleware、CORSMiddleware
给 HTTP 响应配置了 GZip 压缩中间件，当响应数据大于 1000 字节时启用压缩  add_middleware、GZipMiddleware
给 HTTP 请求注册了路由，前缀为 /api/v1，标签为 chat     include_router、prefix、tags
给 WebSocket 请求注册了路由，路径为 /ws     add_api_websocket_route、
【中间件相当于过滤器、拦截器、顾问这些，对请求、响应做处理的】
【路由注册，是让后端知道有哪些接口的，进而转发请求】
"""
# app：Web 应用的入口对象
app = FastAPI(
    title="旅行规划Agent API",
    version="2.0.0",
    description="多Agent智能旅行助手（LangGraph 最佳实践版本）",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # 管理应用启动和关闭时的操作
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],  # 允许所有的请求方法（GET, POST, PUT, DELETE等）
    allow_headers=["*"],  # 允许请求携带所有的 HTTP 头
)

# Gzip压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)  # 压缩响应数据，当响应数据大于1000字节时启用压缩

# 注册路由  把路由统一注册到 app 上，并增加统一前缀；tags 是 Swagger 文档中显示的接口分组标签
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])

# WebSocket路由
app.add_api_websocket_route("/ws", websocket_endpoint)



"""
应用在启动后，访问根路径，会返回这些信息
"""
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "旅行规划Agent API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "websocket": "/ws"
    }



"""
uvicorn 是一个基于 ASGI 的高性能异步 Web 服务器，用于运行 FastAPI 应用。
uvicorn.run() 方法启动应用，指定了应用的模块和对象【app.main、app】、主机地址、端口号、是否启用自动重载以及日志级别。
应用启动之后，监听指定的主机和端口，等待接收 HTTP 请求和 WebSocket 连接。

类似springboot的启动类；

FastAPI 负责路由匹配；routes.py 相当于控制器，负责处理请求和响应；
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )
