from mail import send_mail
import time
from models import BaseStr as redis_, DiaTaskList
from models import VpsConfigModel, PackageConfig, PackageVpsConfig
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


def make_pool(vps_uuid):
    package_namelist = PackageVpsConfig.list_all_package(vps_uuid)
    if not VpsConfigModel.can_share(vps_uuid):
        for package_name in package_namelist:
            is_need_to_set_pool(
                PackageConfig.find_package_by_packagename(package_name), vps_uuid
            )
    else:
        for package_name in package_namelist:
            is_need_to_set_pool(
                PackageConfig.find_package_by_packagename(package_name), vps_uuid
            )
        for package_config in PackageConfig.list_all_package(private=False):
            is_need_to_set_pool(package_config, vps_uuid)


def is_need_to_set_pool(package_config, vps_uuid):
    if package_config["ip_vaild_min"] and package_config["ip_vaild_max"]:
        if (
            redis_.ttl_(f"vps_{vps_uuid}") > package_config["ip_vaild_min"]
            and redis_.ttl_(f"vps_{vps_uuid}") < package_config["ip_vaild_max"]
        ):
            redis_.set_(
                f'{package_config["package_name"]}_{vps_uuid}',
                redis_.get_(f"vps_{vps_uuid}"),
                redis_.ttl_(f"vps_{vps_uuid}"),
            )
    elif package_config["ip_vaild_min"]:
        if redis_.ttl_(f"vps_{vps_uuid}") > package_config["ip_vaild_min"]:
            redis_.set_(
                f'{package_config["package_name"]}_{vps_uuid}',
                redis_.get_(f"vps_{vps_uuid}"),
                redis_.ttl_(f"vps_{vps_uuid}"),
            )
    elif package_config["ip_vaild_max"]:
        if redis_.ttl_(f"vps_{vps_uuid}") < package_config["ip_vaild_min"]:
            redis_.set_(
                f'{package_config["package_name"]}_{vps_uuid}',
                redis_.get_(f"vps_{vps_uuid}"),
                redis_.ttl_(f"vps_{vps_uuid}"),
            )
    else:
        redis_.set_(
            f'{package_config["package_name"]}_{vps_uuid}',
            redis_.get_(f"vps_{vps_uuid}"),
            redis_.ttl_(f"vps_{vps_uuid}"),
        )


def verify_ip(ip_):
    try:
        proxies = {
            "http": f"http://{PROXY_SERVICE_USERNAME}:{PROXY_SERVICE_PASSWORD}@{ip_}:{VPS_PORT}",
            "https": f"http://{PROXY_SERVICE_USERNAME}:{PROXY_SERVICE_PASSWORD}@{ip_}:{VPS_PORT}",
        }
        res = session.get("http://www.baidu.com", timeout=5, proxies=proxies)
        if res.status_code != 200:
            raise
        return True
    except:
        return False


def dia(vps_conf):
    """
        vps 拨号服务器配置
        消费者
    """
    ttl_ = redis_.ttl(f'vps_{vps_conf["vps_uuid"]}')
    if vps_conf["expired_time"] and vps_conf["env_is_ok"]:
        if ttl_ < 30 and ttl_ != -2 and ttl_ != -1:
            if len(redis_.keys("vps_")) < 2:
                # 保持池子不为空
                redis_.set_(
                    f'vps_{vps_conf["vps_uuid"]}',
                    redis_.get_(f'vps_{vps_conf["vps_uuid"]}'),
                    120,
                )
            else:
                redis_.del_(f'vps_{vps_conf["vps_uuid"]}')
                time.sleep(10)
                while True:
                    vps = VpsService(vps_conf["vps_uuid"])
                    ip_ = vps.dia()
                    if ip_ and verify_ip(ip_):
                        redis_.set_(
                            f'vps_{vps_conf["vps_uuid"]}',
                            f"{ip_}:{VPS_PORT}",
                            vps_conf["dia_frequency"],
                        )
                        break
                    else:
                        continue
        make_pool(vps_conf["vps_uuid"])
    return


def package_thread(threading_group, vps_conf):
    """
        threading_group 线程组，防止同一台拨号机同时给出拨号命令
        vps 拨号服务器配置
    """
    if not threading_group.get(vps_conf["vps_uuid"]):
        threading_group[vps_conf["vps_uuid"]] = Thread(
            name=vps_conf["vps_uuid"], target=dia, args=(vps_conf,)
        )
        threading_group[vps_conf["vps_uuid"]].start()
        # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
    else:
        if not threading_group[vps_conf["vps_uuid"]].isAlive():
            threading_group[vps_conf["vps_uuid"]] = Thread(
                name=vps_conf["vps_uuid"], target=dia, args=(vps_conf,)
            )
            threading_group[vps_conf["vps_uuid"]].start()
            # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
        else:
            pass
    return


def consumer_dia():
    threading_group = {}
    while True:
        if DiaTaskList.llen_():
            vps_uuid = DiaTaskList.rpop_(True)
            package_thread(
                threading_group, VpsConfigModel.find_config_by_vps_uuid(vps_uuid)
            )
        else:
            DiaTaskList.push_empty_list(VpsConfigModel.list_all_vps_uuid())
