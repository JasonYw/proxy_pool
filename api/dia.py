from mail import send_mail
import time
from models import BaseStr as redis_
from models import VpsConfigModel, PackageConfig
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


def find_package_by_ttl(ttl_):
    for i in PackageConfig.list_all_package():
        if ttl_ > i.get("ip_vaild_min") and ttl_ < i.get("ip_vaild_max"):
            yield i.get("package_name"), True
        elif not i.get("ip_vaild_min") and not i.get("ip_vaild_max"):
            yield i.get("package_name"), True
        else:
            yield i.get("package_name"), False


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
    if not vps_conf["env_is_ok"]:
        vps = VpsService(vps_conf["vps_uuid"])
        if vps.deployment():
            VpsConfigModel.update_env(vps_conf["vps_uuid"])
            vps_conf["env_is_ok"] = True
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
        ttl_ = redis_.get_(f'vps_{vps_conf["vps_uuid"]}')
        for x, y in find_package_by_ttl(ttl_):
            if y:
                redis_.set_(f'{x}_{vps_conf["vps_uuid"]}', f"{ip_}:{VPS_PORT}", ttl_)
            else:
                redis_.del_key(f'{x}_{vps_conf["vps_uuid"]}')
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
        allconfig = VpsConfigModel.list_all_vps_by_env_is(True)
        if not allconfig:
            time.sleep(60)
        else:
            for vps_conf in allconfig:
                package_thread(threading_group, vps_conf)


if __name__ == "__main__":
    pass
