import asyncio,logging

import aiomysql 

def log(sql,args=()):
	logging.info('SQL:%s'% sql)
#记录sql语句的参数的

async def create_pool(loop,**kw):
	#这个kw参数将会从配置文件中获得
	logging.info('create database connection pool...')
	global __pool
#定义全局变量__pool在这个模块中的任何地方都可以使用
	__pool=await aiomysql.create_pool(
		host=kw.get('host','localhost'),
#数据库服务器运行的地址，如果配置文件中没有就用默认的localhost
		port=kw.get('port',3306),
#运行的端口
		user=kw['user'],
#用户名
		password=kw['password'],
#用户密码
		db=kw['db']
#要链接的数据库名
		charset=kw.get('charset','utf8')
#默认的编码，服务器，数据库，表格都可以单独设置编码，如果没有设置默认的继承他的上一层的编码
		autocommit=kw.get('autocommit',True),
#自动提交会话，这样就不用我们手动去提交了
		maxsize=kw.get('maxsize',10),
		minsize=kw,get('minsize',1)
#这两个参数不太了解。可能是数据库的最大和最小链接数？？？
		loop=loop
#事件循环
			)


****************************************************************
#这是数据库中的select（查）
async def select(sql,args,size=None):
	log(sql,args)
	global __pool
	async with __pool.get() as conn:
#with 上下文管理，as在数据库中有重命名的意思，在这也差不多。
		async with conn.cursor(aiomysql.DictCursor) as cur:
#创建游标
			await cur.execute(sql.replace('?','%s'),args or ())
#replace是用来替换的作用。在sql语句中使用?代替参数的，而mysql中是用 %s 来代替的。
#or 具有短路算法。
			if size:
				rs=await cur.fetchmany(size)
			else:
				rs=await cur.fetchall()
#如果有size参数的话。我们就会从已有的全部结果中显示部分结果。
		logging.info('rows returned:%s'%len(rs))
		return rs
###############################################################
#这是Insert,Update,Delete(增,改,删)三个公用一个函数，因为他们需要的参数相同
async def execute(sql,args,autocommit=True):
	log(sql)
#这里添加autocommit的原因是。在我们执行这三个操作时可能中途会出现意外情况，这样数据库就会出现问题。所有我们手动提价，当出现问题时　就回退到提交之前的状态。
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?','%s'),args)
				affected=cur.rowcount
#获得操作的行数
			if not autocommit:
				await conn.commit()
			except BaseException as e:
				if not autocommit:
					await conn.rollback()
				raise 
			return affected
****************************************************************
def create_args_string(num):
	L=[]
	for n in range(num):
		L.append('?')
	return ','.join(L)
#根据参数个数来添加参数的占位符
****************************************************************
#ORM的关键之处就是用对象来表示出数据库的结构，Field就是用对象来表示出数据库中表的结构
class Field(object):
	def __init__(self,name,column_type,primary_key,default):
		self.name=name
		self.column_type=column_type
		self.primary_key=primary_key
		self.default=default
#因为所有的子Field都需要上面这种保存的参数。所以我们集成到父类中避免重复代码。
	def __str__(self):
		return '<%s,%s:%s>'%(self.__class__.name__,self.column_type,self.name)
class StringField(Field):
	def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)
class BooleanField(Field):
	def __init__(self,name=None,default=False):
		super().__init__(name,'boolean',False,default)
class IntegerField(Field):
	def __init__(self,name=None,primary_key=False,default=0):
		super().__init__(name,'bigint',primary_key,default)
class FloatField(Field):
	def __init__(self,name=None,primary_key=False,default=0.0):
		super().__init__(name,'real',priamry_key,default)
class TextField(Field):
	def __init__(self,name=None,default=None):
		super().__init__(name,'text',False,default)
################################################################
class ModelMetaclass(type):
	def __new__(cls,name,bases,attrs):
		if name=='Model':
			return type.__new__(cls,name,bases,attrs)
#过滤掉Model这个父类。不做修改直接返回
		tableName=attrs.get('__table__',None) or name
#表的名字
		logging.info('found model:%s (table:%s)'%(name,tableName))
		mappings=dict()
		fields=[]
		primaryKey=None
		for k,v in attrs.items():
			if isinstance(v,Field):
				logging.info('found mapping:%s==>%s'%(k,v))
				mappings[k]=v
#找到属于表的属性放入映射中
				if v.primary_key:
					if primaryKey:
						raise StandardError('Duplicate priamry key for field:%s'% k)
					primaryKey=k
				else:
					fields.append(k)
		if not primarykey:
			raise StandardError('Primary key not found ')
#找到有主键的一列并验证是否唯一，并把主键存储在primaryKey中。
#不是主键一列的列名放入fields中。		
		for k in mappings.keys():
			attrs.pop(k)
#在后面的父类Model中定义了__setattr__和__getattr__这两个特殊变量。所以其实他的子类是没有__dict__这个变量的，这个里的attrs可能是父类的__dict__。并且在这种情况下。类的属性不同于一般情况，类的属性是可以覆盖实例的属性的。所以我们需要删除类的属性.>>>(只是一个猜测，以后验证)<<<
		escaped_fields=list(map(lambda f:'`%s`'% f,fields))
#这好像是在mysql中使用的，原因是避免我们的字段名字与保留关键字重名。所以用 ``　引起来。来区别不同。

		attrs['__mappings__']=mappings
		attrs['__table__']=tableName
		attrs['__primary_key__']=primaryKey
		attrs['__fields__']=fields
		attrs['__select__']='select `%s`,%s from `%s`'%(primaryKey,','.join(escaped_fields),tableName)
#select * from tablename
		attrs['__insert__']='insert into `%s`(%s,`%s`) values(%s)'%(tableName,','.join(escaped_fields),priamryKey),create_args_string(len(escaped_fields)+1)
#insert into tablename(*) values (?,?,?...)
		attrs['__update__']='update `%s` set %s where `%s`=?'%(tableName,','.join(map(lambda f:'`%s`=?'%(mappings.get(f).name or f),fields)),primarykey)
#update tablename set fields=? where primarykey=?
		attrs['__delete__']='delete from `%s` where `%s`=?'%(tableName,primaryKey)
#delete from tablename where primaryKey
		return type.__new__(cls,name,bases,attrs)
#总结下来元类的作用就是用对象把数据库的表，表的结构,slq语句等等表示出来，方便以后的使用。以后我们想要操作数据库就不用接触数据库了直接用对象来代替数据库。

***************************************************************	
class Model(dict,metaclass=ModelMetaclass):
	def __init__(self,**kw):
		super(Model,self).__init__(**kw)
	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute '%s'"%key)
#这里不能设置　self.name这样的取值方式，因为这样会调用他自设，也会进入无限循环中去
	def __setattr__(self,key,value):
		self[key]=value
#在这里不能使用self.name=name这样的方式赋值，因为这样就会在这里又会调用他自身，就会进入一个无限循环中。
	def getValue(self,key):
		return getattr(self,key,None)
	def getValueOrDefault(self,key):
		value=getattr(self,key,None)
		if value is None:
			field=self.__mappings__[key]
			if field.default is not None:
				value=field.default() if callable(fielld,default) else field.default
				logging.debug('using default value for %s:%s'% (key,str(value)))
				setattr(self,key,value)
		return value
#如果实例的某一个列没有设置值，那么就取这列的默认值。
*****************************************************************

	@classmethod
#classmethod装饰的函数，不用创建实例，直接类就可以使用。也就是类的方法。
	async def findAll(cls,where=None,args=None,**kw):
		'find objects by where clause.'
		 sql=[cls.__select__]
		 if where:
			sql.append('where')
			sql.append(where)
#选择条件
		if args is None:
			args=[]
		orderBy=kw.get('orderBy',None)
		if orderBy:
#排序　			
			sql.append('order by')
			sql.append(orderBy)
		limit=kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
		elif isinstance(limit,tuple) and len(limit) == 2:
			sql.apend('?,?')
			args.extend(limit)
#limit是用来限制查询结果的条数。有两种表示方法int和tuple
		else:
			raise ValueError('Invalid limit value:%s'%str(limit))
	rs= await select(''.join(sql),args)
#这个rs的结果好像是在list里每条结果用一个tuple表示的
	return [cls(**r) for r in rs]
#cls(**r) 得到的结果就是一个dict，因为他的父类是dict。
#############################################################
	@classmathod
	async def findNumber(cls,selectField,where=None,args=None):
		'find nubmer by select and where '
		 sql=['select %s _num_ from `%s`'(selectField,cls.__table__)]		
		 if where:
			sql.append('where')
			sql.append(where)
		rs=await select(''.join(sql),args,1)
		if len(rs)==0:
			return None
		return rs[0]['_num_']
#这是用来计数的		 
#查询某个值有多少个
##############################################################	
	@classmathod
	async def find(cls,pk):
		'find object by primary key.'
		 rs=await select('%s where `%s`=?'%(cls.__select__,cls.__primary_key__),[pk],1)
#查找是否有某一个主键的数据
		if len(rs)==0:
			return None
		return cls(**rs[0])
###############################################################
	async def save(self):
		args=list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows=await execute(self.__insert__,args)
		if rows !=1:
			logging.wran('failed to insert record:affected rows:%s'% rows)
	async def update(self):
		args=list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows=await execute(self.__update__,args)
		if rows !=1:
			logging.warn('failed to update by primary key:affected rows:%s'% rows)

	async def remove(self):
		args=[self.getValue(self.__priamry_key__)]
		rows=await execute(self.__delete__,args)
		if row !=1:
			logging.warn('failed to remove by primary key:affected rows:%s'%rows)
#增，删，改操作。















		




























	



				











































































































































































































































