import pymysql
import configparser
import os
abspath =os.path.abspath(__file__).replace(f'/{os.path.basename(__file__)}','')
config = configparser.ConfigParser()
config.read(f'{abspath}/conf.ini')
MYSQL_HOST=config['MYSQL']['MYSQL_HOST']
MYSQL_PORT=config['MYSQL']['MYSQL_PORT']
MYSQL_USER=config['MYSQL']['MYSQL_USER']
MYSQL_PASS=config['MYSQL']['MYSQL_PASS']
MYSQL_DB=config['MYSQL']['MYSQL_DB']

def connect_mysql():
    '''
        连接mysql
        name：mysql名字
        host：mysql节点ip
        port：端口号
        database：数据库
        user:用户
        password：密码
    '''
    return pymysql.connect(host=MYSQL_HOST,port=int(MYSQL_PORT),user=MYSQL_USER,database=MYSQL_DB,password=MYSQL_PASS)


class BaseModel:
    '''
        封装mysql常用函数
    '''
    __db = connect_mysql()
    __table = ''
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
    '''
        存储拨号机的配置信息
    '''
    __table = 'service_vpsconfig'

    @classmethod
    def list_all_vps(cls):
        cls.cursor.execute(f'SELECT * FROM {cls.__table}')
        results =  cls.cursor.fetchall()
        cls.close()
        return results

class VpsMonitorModel(BaseModel):
    __table = 'service_vpsmonitor'
    
    @classmethod
    def insert_monitor(cls,vps_uuid,alive,MemTotal,MemFree,MemAvailable,cpu_user,cpu_sys,cpu_idle,eth0_Receive,eth0_Transmit):
        cls.cursor.execute(f'INSERT INTO {cls.__table} SET alive = {alive}, MemTotal = {MemTotal}, MemFree = {MemFree},MemAvailable = {MemAvailable}, cpu_user={cpu_user}, cpu_sys= {cpu_sys},cpu_idle = {cpu_idle},eth0_Receive={eth0_Receive},eth0_Transmit ={eth0_Transmit},vps_uuid = {vps_uuid}')
        cls.__db.commit()
        cls.close()

    


# class PackageConfig(BaseModel):
#     __table = 'agent_packageconfig'

#     @classmethod
#     def list_all_package(cls):
#         results = cls.cursor.execute(f'SELECT * FROM {cls.__table}')

