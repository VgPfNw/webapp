import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

def init_jinja2(app, **kw):
#初始化jinja2	
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
#是否转义，把<>&的等字符转换为&lt;&gt;&amp		
        block_start_string = kw.get('block_start_string', '{%'),
#代码块的开始标识符		
        block_end_string = kw.get('block_end_string', '%}'),
#代码块的结束标识符		
        variable_start_string = kw.get('variable_start_string', '{{'),
#变量的开始标识符
        variable_end_string = kw.get('variable_end_string', '}}'),#变量的结束标识符
        auto_reload = kw.get('auto_reload', True)
#模块修改后的重新加载		
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
#获取模板文件的路径	
    env = Environment(loader=FileSystemLoader(path), **options)
#这是一个类用来保存配置，全局对象，等等	
    filters = kw.get('filters', None)
#这是一个过滤器	
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env
*******************************************************************************************************************************
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger
#这是一个日志拦截器，在函数被RequestHandler处理之前作用与函数。	
	

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data
#这也是一个请求的数据的拦截器，在函数被RequestHandler处理之前作用与函数，

async def response_factory(app, handler):
#响应拦截器，是在根据处理函数返回的结果，响应不同的内容
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
#如果是streamResponse直接返回
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
#如果是字节流，加入到body中返回
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
#如果是重定向，就重新处理				
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
#否则加入到响应的body中			
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
#如果是类似与api的返回结果join，就序列化后加入到body中				
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
#否则就是放入到模板中的变量，并代入到模板中返回html				
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response
#数据类型就是响应码之类的
#################################################################################
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)
#时间过滤器

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www', password='www', db='awesome')
#后面将从配置文件中获取。	
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
