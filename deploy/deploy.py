from mail import send_mail
import time
from models import DeployTaskList
from models import VpsConfigModel
from vps import VpsService
import requests
import configparser
import os
from threading import Thread


def deploy(vps_conf):
    """
        vps 拨号服务器配置
        消费者
    """
    if not vps_conf["env_is_ok"]:
        vps = VpsService(vps_conf["vps_uuid"])
        if vps.deployment():
            VpsConfigModel.update_env(vps_conf["vps_uuid"])
    return


def package_thread(threading_group, vps_conf):
    """
        threading_group 线程组，防止同一台拨号机同时给出拨号命令
        vps 拨号服务器配置
    """
    if not threading_group.get(vps_conf["vps_uuid"]):
        threading_group[vps_conf["vps_uuid"]] = Thread(
            name=vps_conf["vps_uuid"], target=deploy, args=(vps_conf,)
        )
        threading_group[vps_conf["vps_uuid"]].start()
        # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
    else:
        if not threading_group[vps_conf["vps_uuid"]].isAlive():
            threading_group[vps_conf["vps_uuid"]] = Thread(
                name=vps_conf["vps_uuid"], target=deploy, args=(vps_conf,)
            )
            threading_group[vps_conf["vps_uuid"]].start()
            # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
        else:
            pass
    return


def consumer_deploy():
    threading_group = {}
    while True:
        if DeployTaskList.llen_():
            vps_uuid = DeployTaskList.rpop_(True)
            package_thread(
                threading_group, VpsConfigModel.find_config_by_vps_uuid(vps_uuid)
            )
        else:
            DeployTaskList.push_empty_list(VpsConfigModel.list_all_vps_uuid())


if __name__ == "__main__":
    pass
