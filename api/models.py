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
    def list_all_vps_by_env_is(cls, env_is):
        if env_is:
            cls.cursor.execute(f"SELECT * FROM {cls.__table} WHERE env_is_ok")
        else:
            cls.cursor.execute(f"SELECT * FROM {cls.__table} WHERE not env_is_ok")
        results = cls.cursor.fetchall()
        cls.close()
        return results

    @classmethod
    def update_env(cls, vps_uuid):
        cls.cursor.execute(
            f"UPDATE {cls.__table} SET env_is_ok = true WHERE vps_uuid = {vps_uuid}"
        )
        cls.__db.commit()
        cls.close()


class PackageConfig(BaseModel):
    __table = "agent_packageconfig"

    @classmethod
    def list_all_package(cls):
        results = cls.cursor.execute(f"SELECT * FROM {cls.__table}")


class PackageUserConfig(BaseModel):
    __table = "agent_package_user"


if __name__ == "__main__":
    pass
