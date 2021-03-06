import pymysql
import configparser
import os
import redis

abspath = os.path.abspath(__file__).replace(f"/{os.path.basename(__file__)}", "")
config = configparser.ConfigParser()
config.read(f"{abspath}/conf.ini")
MYSQL_HOST = config["MYSQL"]["MYSQL_HOST"]
MYSQL_PORT = config["MYSQL"]["MYSQL_PORT"]
MYSQL_USER = config["MYSQL"]["MYSQL_USER"]
MYSQL_PASS = config["MYSQL"]["MYSQL_PASS"]
MYSQL_DB = config["MYSQL"]["MYSQL_DB"]
REDIS_HOST = config["REDIS"]["REDIS_HOST"]
REDIS_PORT = config["REDIS"]["REDIS_PORT"]
REDIS_DB = config["REDIS"]["REDIS_DB"]
REDIS_PASS = config["REDIS"]["REDIS_PASS"]
REDISPOOL = None


def connect_redis():
    """
        负责连接redis
        name：redis的名字
        host：redis的ip
        port：端口号
        db：redis库
        是否需要提前解码
    """
    global REDISPOOL
    if not REDISPOOL:
        REDISPOOL = redis.Redis(
            connection_pool=redis.ConnectionPool(
                host=REDIS_HOST,
                port=int(REDIS_PORT),
                db=int(REDIS_DB),
                password=MYSQL_PASS,
                decode_responses=True,
            )
        )
    return REDISPOOL


def connect_mysql():
    """
        连接mysql
        name：mysql名字
        host：mysql节点ip
        port：端口号
        database：数据库
        user:用户
        password：密码
    """
    return pymysql.connect(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        database=MYSQL_DB,
        password=MYSQL_PASS,
    )


class BaseModel:
    """
        封装mysql常用函数
    """

    __db = connect_mysql()
    __table = ""
    cursor = __db.cursor(pymysql.cursors.DictCursor)

    @classmethod
    def close(cls):
        try:
            cls.cursor.close()
        except:
            pass
        try:
            cls.__db.close()
        except:
            pass


class BaseList:
    """
        对于redis为list封装
    """

    db = connect_redis()
    __key = None
    __lock = f"{__key}_lock"

    @classmethod
    def lpush_(cls, data):
        return cls.db.lpush(cls.__key, data)

    @classmethod
    def lpop_(cls, lrem_=False):
        if lrem_:
            while True:
                if cls.db.incr(cls.__lock) == 1:
                    result = cls.db.lpop(cls.__key)
                    cls.db.lrem(cls.__key, 0, result)
                    cls.db.delete(cls.__lock)
                    break
        else:
            result = cls.db.lpop(cls.__key)
        return result

    @classmethod
    def rpush_(cls, data):
        return cls.db.rpush(cls.__key, data)

    @classmethod
    def rpop_(cls, lrem_=False):
        if lrem_:
            while True:
                if cls.db.incr(cls.__lock) == 1:
                    result = cls.db.rpop(cls.__key)
                    cls.db.lrem(cls.__key, 0, result)
                    cls.db.delete(cls.__lock)
                    break
        else:
            result = cls.db.rpop(cls.__key)
        return result

    @classmethod
    def llen_(cls):
        return cls.db.llen(cls.__key)

    @classmethod
    def push_empty_list(cls, list_):
        if isinstance(list_, list):
            while True:
                if cls.db.incr(cls.__lock) == 1:
                    if not cls.llen_():
                        for i in list_:
                            cls.lpush_(i)
                    cls.db.delete(cls.__lock)
                    return None


class WatchTaskList(BaseList):
    __key = "proxy_watch_task_list"


class VpsConfigModel(BaseModel):
    """
        存储拨号机的配置信息
    """

    __table = "service_vpsconfig"

    @classmethod
    def list_all_vpsuuid(cls):
        cls.cursor.execute(f"SELECT vps_uuid FROM {cls.__table}")
        results = list(map(lambda x: x["vps_uuid"], cls.cursor.fetchall()))
        cls.close()
        return results

    @classmethod
    def find_config_by_vpsuuid(cls, vps_uuid):
        cls.cursor.execute(f"SELECT * FROM {cls.__table} WHERE vps_uuid ='{vps_uuid}'")
        results = cls.cursor.fetchone()
        cls.close()
        return results


class VpsMonitorModel(BaseModel):
    __table = "service_vpsmonitor"

    @classmethod
    def insert_monitor(
        cls,
        vps_uuid,
        alive,
        MemTotal,
        MemFree,
        MemAvailable,
        cpu_user,
        cpu_sys,
        cpu_idle,
        eth0_Receive,
        eth0_Transmit,
    ):
        cls.cursor.execute(
            f"INSERT INTO {cls.__table} SET alive = {alive}, MemTotal = {MemTotal}, MemFree = {MemFree},MemAvailable = {MemAvailable}, cpu_user={cpu_user}, cpu_sys= {cpu_sys},cpu_idle = {cpu_idle},eth0_Receive={eth0_Receive},eth0_Transmit ={eth0_Transmit},vps_uuid = {vps_uuid}"
        )
        cls.__db.commit()
        cls.close()
