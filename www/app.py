import logging
logging.basicConffig(level=logging.INFO)
#运行服务时会显示logging.INFO等级以上的日志信息
import asyncio,os,json,time
from datetime import datetime

from aiohttp import web

def index(request):
    return web.Response(body=b'<h1>Awesome</h1>')

@asyncio.coroutine
def init(loop):
    app=web.Application(loop=loop)
    #创建应用
    app.router.add_route('GET','/',index)
    #添加处理函数的路径
    srv=yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
    #当放在公网上时这个ip地址不需要修改。
    logging.info('server started at http://127.0.0.1:9000...')
    return srv
loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
#得到循环事件
#等待事件并处理事件
