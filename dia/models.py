import pymysql
import configparser
import redis
import os

abspath = os.path.abspath(__file__).replace(f"/{os.path.basename(__file__)}", "")
config = configparser.ConfigParser()
config.read(f"{abspath}/conf.ini")


REDIS_HOST = config["REDIS"]["REDIS_HOST"]
REDIS_PORT = config["REDIS"]["REDIS_PORT"]
REDIS_DB = config["REDIS"]["REDIS_DB"]
REDIS_PASS = config["REDIS"]["REDIS_PASS"]
MYSQL_HOST = config["MYSQL"]["MYSQL_HOST"]
MYSQL_PORT = config["MYSQL"]["MYSQL_PORT"]
MYSQL_USER = config["MYSQL"]["MYSQL_USER"]
MYSQL_PASS = config["MYSQL"]["MYSQL_PASS"]
MYSQL_DB = config["MYSQL"]["MYSQL_DB"]
REDISPOOL = None


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


class BaseStr:
    """
        对于redis为str类型的封装
    """

    db = connect_redis()

    @classmethod
    def ttl_(cls, key):
        """
            -1 无时间限制
            -2 无此key
        """
        return cls.db.ttl(key)

    @classmethod
    def set_(cls, key, vlaue, timeout=None):
        return cls.db.set(key, vlaue, timeout)

    @classmethod
    def get_(cls, key):
        try:
            return cls.db.get(key)
        except:
            return None

    @classmethod
    def del_key(cls, key):
        return cls.db.delete(key)

    @classmethod
    def get_ttl_of_key(cls, key):
        """
            -1 无时间限制
            -2 无此key
        """
        return cls.db.ttl(key)

    @classmethod
    def len_pool(cls, key):
        return len(cls.db.keys(key))


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


class DiaTaskList(BaseList):
    __key = "proxy_dia_task_list"


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


class VpsConfigModel(BaseModel):
    """
        存储拨号机的配置信息
    """

    __table = "agent_vpsconfig"

    @classmethod
    def find_config_by_vps_uuid(cls, vpd_uuid):
        cls.cursor.execute(
            f'SELECT * FROM {cls.__table} WHERE vps_uuid="{vpd_uuid}" AND env_is_ok LIMIT 1'
        )
        result = cls.cursor.fetchone()
        cls.close()
        return result

    @classmethod
    def list_all_vps_uuid(cls):
        cls.cursor.execute(f"SELECT vps_uuid FROM {cls.__table} WHERE env_is_ok")
        results = list(map(lambda x: x["vps_uuid"], cls.cursor.fetchall()))
        cls.close()
        return results

    @classmethod
    def can_share(cls, vps_uuid):
        cls.cursor.execute(
            f'SELECT * FROM {cls.__table} WHERE SHARE AND vps_uuid="{vps_uuid}" LIMIT 1'
        )
        result = cls.cursor.fetchone()
        cls.close()
        if result:
            return True
        else:
            return False


class PackageConfig(BaseModel):
    __table = "agent_packageconfig"

    @classmethod
    def list_all_package(cls, private):
        if private:
            cls.cursor.execute(f"SELECT * FROM {cls.__table} WHERE private")
        else:
            cls.cursor.execute(f"SELECT * FROM {cls.__table} WHERE NOT private")
        results = cls.cursor.fetchall()
        cls.cursor.close()
        return results

    @classmethod
    def find_package_by_packagename(cls, package_name):
        cls.cursor.execute(
            f'SELECT * FROM {cls.__table} WHERE package_name="{package_name}" LIMIT 1'
        )
        results = cls.cursor.fetchone()
        cls.cursor.close()
        return results


class PackageUserConfig(BaseModel):
    __table = "agent_package_user"


class PackageVpsConfig(BaseModel):
    __table = "agent_package_vps"

    @classmethod
    def list_all_package(cls, vps_uuid):
        cls.cursor.execute(f'SELECT * FROM {cls.__table} WHERE vps_uuid = "{vps_uuid}"')
        results = list(map(lambda x: x["package_name"], cls.cursor.fetchall()))
        cls.cursor.close()
        return results
