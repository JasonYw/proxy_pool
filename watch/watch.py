from mail import send_mail
import time
from models import VpsConfigModel, VpsMonitorModel, WatchTaskList
from vps import VpsService
import requests
import configparser
import os
from threading import Thread

abspath = os.path.abspath(__file__).replace(f"/{os.path.basename(__file__)}", "")
config = configparser.ConfigParser()
config.read(f"{abspath}/conf.ini")
VPS_PORT = config["VPS"]["VPS_PORT"]
PROXY_SERVICE_USERNAME = config["PROXY"]["PROXY_SERVICE_USERNAME"]
PROXY_SERVICE_PASSWORD = config["PROXY"]["PROXY_SERVICE_PASSWORD"]
session = requests.Session()


def watch(vps_conf):
    """
        vps 拨号服务器配置
        消费者
    """
    vps = VpsService(vps_conf["vps_uuid"])
    result = vps.watch()
    VpsMonitorModel.insert_monitor(vps_conf["vps_uuid"], **result)
    return


def package_thread(threading_group, vps_conf):
    """
        threading_group 线程组，防止同一台拨号机同时给出拨号命令
        vps 拨号服务器配置
    """
    if not threading_group.get(vps_conf["vps_uuid"]):
        threading_group[vps_conf["vps_uuid"]] = Thread(
            name=vps_conf["vps_uuid"], target=watch, args=(vps_conf,)
        )
        threading_group[vps_conf["vps_uuid"]].start()
        # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
    else:
        if not threading_group[vps_conf["vps_uuid"]].isAlive():
            threading_group[vps_conf["vps_uuid"]] = Thread(
                name=vps_conf["vps_uuid"], target=watch, args=(vps_conf,)
            )
            threading_group[vps_conf["vps_uuid"]].start()
            # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
        else:
            pass
    return


def consumer_watch():
    threading_group = {}
    while True:
        if WatchTaskList.llen_():
            vps_uuid = WatchTaskList.rpop_(True)
            package_thread(
                threading_group, VpsConfigModel.find_config_by_vpsuuid(vps_uuid)
            )
        else:
            WatchTaskList.push_empty_list(VpsConfigModel.list_all_vpsuuid())
