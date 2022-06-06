from fastapi import FastAPI, Query, Response, Path, Depends
from fastapi.responses import JSONResponse
from fastapi import Request
import random
import uvicorn
import aioredis
import aiomysql
import datetime
import time
import os
import configparser
from apscheduler.schedulers.background import BackgroundScheduler
from copy import deepcopy


app = FastAPI()
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


RESPONSE_RESULT = {"state": 200, "data": []}

"""
    启动，结束api
"""


@app.on_event("startup")
async def startup_event():
    app.state.redis = await aioredis.create_redis(
        address=(REDIS_HOST, int(REDIS_PORT)),
        db=int(REDIS_DB),
        encoding="utf-8",
        password=REDIS_PASS,
    )
    app.state.pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        password=MYSQL_PASS,
        db=MYSQL_DB,
    )


@app.on_event("shutdown")
async def shutdown_event():
    app.state.redis.close()
    await app.state.redis.wait_closed()
    app.state.pool.close()
    # global SCHED
    # SCHED.shutdown()


"""
    封装redis，mysql
"""


async def r_keys(request, key):
    return await request.app.state.redis.keys(key)


async def r_hset(request, key, value):
    return await request.app.state.redis.hset(key, *value)


async def r_exists(request, key):
    return await request.app.state.redis.r_exists(key)


async def r_hgetall(request, key):
    return await request.app.state.redis.hgetall(key)


async def r_get(request, key):
    return await request.app.state.redis.get(key)


async def r_set(request, key, value):
    return await request.app.state.redis.set(key, value)


async def r_ttl(request, key):
    await request.app.state.redis.ttl(key)


async def r_scard(request, key):
    await request.app.state.redis.r_scard(key)


async def r_sadd(request, key, value):
    await request.app.state.redis.sadd(key, value)


async def m_find_one(request, sql_):
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    await cur.execute(sql_)
    result = await cur.fetchone()
    await cur.close()
    return result


async def m_find_all(request, sql_):
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    await cur.execute(sql_)
    result = await cur.fetchall()
    await cur.close()
    return result


"""
    处理验证
"""


async def set_package_to_redis_by_mysql(request: Request, packagename: str):
    result = await m_find_one(
        request,
        f'SELECT * FROM agent_packageconfig WHERE package_name ="{packagename}" LIMIT 1',
    )
    if not result:
        return False
    else:
        config = []
        for i, j in result.items():
            config.append(i)
            config.append(j)
        await r_hset(request, packagename, tuple(config))
        return True


async def auth_superuser(request, username):
    key_ = f"superuser_{username}"
    if await r_exists(request, key_):
        if not await r_get(request, key_):
            return False
    else:
        result = await m_find_all(
            request,
            f'SELECT * FROM agent_userconfig WHERE username="{username}" LIMIT 1',
        )
        await r_set(request, key_, result["is_superuser"])
        if not result["is_superuser"]:
            return False
    return True


async def auth_username_password(request, username, password):
    if await r_get(request, username) == password:
        return True
    else:
        cur = await request.state.pool.cursor(aiomysql.DictCursor)
        result = await cur.execute(
            f'SELECT * FROM agent_userconfig WHERE username="{username}" AND password="{password}" LIMIT 1'
        )
        await cur.close()
        if result:
            await request.state.redis.set(username, password)
            return True
        else:
            return False


async def auth_expired_time(request, username, packagename, id):
    key_ = f"{username}&{packagename}&{id}&expired_time"
    if await r_exists(request, key_):
        if isinstance(await r_get(request, key_), int):
            if await r_get(request, key_) < int(time.time()):
                return False
    else:
        result = await m_find_all(
            request,
            f'SELECT * FROM agent_packageuser WHERE username="{username}" AND packagename="{packagename}" AND id={id} LIMIT 1',
        )
        await r_set(request, key_, result["expired_time"])
        if result["expired_time"] < int(time.time()):
            return False
    return True


async def auth_api_package(request, username, packagename, id):
    today = time.mktime(datetime.date.today().timetuple())
    package = await r_hgetall(request, packagename)
    rule = {
        "ip_per_day": f"{username}&{packagename}&{id}&ip_per_{today}",
        "ip_per_package": f"{username}&{packagename}&{id}&ip_per_package",
    }
    for i, j in rule.items():
        if isinstance(package.get(i), int):
            if await r_exists(request, j):
                if len(await r_scard(request, j)) > package[i]:
                    return False
            else:
                result = await m_find_all(
                    request,
                    f'SELECT * FROM agent_userrecord WHERE user_package_key ="{j}"',
                )
                if result:
                    for i in result:
                        await r_sadd(request, j, i["ip"])
                    if len(result) > package[i]:
                        return False
    return True


async def auth_tunnel_package(request, username, packagename, id):
    today = time.mktime(datetime.date.today().timetuple())
    package = await r_hgetall(packagename)
    rule = {
        "tunnel_per_day": f"{username}&{packagename}&{id}&tunnel_per_{today}",
        "tunnel_per_package": f"{username}&{packagename}&{id}&tunnel_per_package",
    }
    for i, j in rule.items():
        if isinstance(package.get(i), int):
            if await r_exists(request, j):
                if await r_get(request, j) > package[i]:
                    return False
            else:
                result = await m_find_one(
                    request,
                    f'SELECT * FROM agent_userrecord WHERE user_package_key ="{j}" LIMIT 1',
                )
                if result:
                    await r_set(request, j, result["count"])
                    if result["count"] > package[i]:
                        return False
    return True


async def auth_user(request: Request, username: str, password: str):
    username, packagename, id_, kind = username.split(
        "&"
    )  # [username,packagename,id,api\tunnel]
    package = await r_hgetall(packagename)
    if not await auth_username_password(request, username, password):
        return False
    if await auth_superuser(request, username):
        return True
    if not package:
        if not await set_package_to_redis_by_mysql(request, packagename):
            return False
    if not await auth_expired_time(request, username, packagename, id_):
        return False
    if kind == "api":
        if await auth_api_package(request, username, packagename, id_):
            return False
    elif kind == "tunnel":
        if await auth_tunnel_package(request, username, packagename, id_):
            return False
    else:
        return False
    return True


@app.get("/auth_for_vps", response_class=JSONResponse)
async def auth_(request: Request, username: str, password: str, local_ip: str):
    global RESPONSE_RESULT
    result = deepcopy(RESPONSE_RESULT)
    if not await auth_user(request, username, password):
        result["data"] = "验证失败"
        result["state"] = 400
    else:
        result["data"] = "验证成功"
    return JSONResponse(result)


"""
    用户提取代理api
"""


async def ttl_(request, key_, min, max):
    ttl_ = await r_ttl(request, key_)
    if ttl_ > min and ttl_ < max:
        return ttl_
    else:
        return False


# @app.get("/get_ip", response_class=JSONResponse)
# async def auth_(request: Request, username: str, password: str):
#     global RESPONSE_RESULT
#     result = deepcopy(RESPONSE_RESULT)
#     package = await auth_user(request, username, password)
#     if package:
#         used_ip = set(
#             await request.app.state.redis.smembers(
#                 f"{username}_{int(time.mktime(datetime.date.today().timetuple()))}"
#             )
#         )
#         keyslist = tuple(
#             await request.app.state.redis.keys(f'{username.split("&")[1]}')
#         )
#         proxy_ips = set(await request.app.state.redus.megt(keyslist))
#         if package.get("ip_per_api_rqs"):
#             result["data"] = list(proxy_ips - used_ip)[: package["ip_per_api_rqs"]]
#         else:
#             result["data"] = [random.choice(list(proxy_ips - used_ip))]
#     return JSONResponse(result)


"""
    处理监听套餐变化
"""


async def find_package_rule(request: Request, package_name):
    packageconfig = await m_find_one(
        request,
        f'SELECT * FROM agent_packageconfig WHERE package_name = "{package_name}" LIMIT 1',
    )
    return packageconfig


async def find_vps_by_packagename(request: Request, package_name):
    vpsuuid_list = []
    packageconfig = await m_find_all(
        request, f'SELECT * FROM agent_packagevps WHERE package_name = "{package_name}"'
    )
    for i in packageconfig:
        vpsuuid_list.append(i["vps_uuid"])
    return vpsuuid_list


async def find_vps_by_share(request: Request, share: bool):
    vpsuuid_list = []
    if share:
        vpsconfig = await m_find_all(
            request, f"SELECT * FROM agent_vpsconfig WHERE share"
        )
    else:
        vpsconfig = await m_find_all(
            request, f"SELECT * FROM agent_vpsconfig WHERE NOT share"
        )
    for i in vpsconfig:
        vpsuuid_list.append(i["vps_uuid"])
    return vpsuuid_list


async def is_need_to_set_pool(request, package_config, vps_uuid):
    if package_config["api_ip_vaild_min"] or package_config["api_ip_vaild_max"]:

        ttl_ = await r_ttl(request, f"vps_{vps_uuid}")
        if (
            ttl_ > package_config["api_ip_vaild_min"]
            and ttl_ < package_config["api_ip_vaild_max"]
        ):
            await r_set(
                request,
                f'{package_config["package_name"]}_{vps_uuid}',
                await r_get(request, f"vps_{vps_uuid}"),
                await r_ttl(request, f"vps_{vps_uuid}"),
            )
    elif package_config["api_ip_vaild_min"]:

        ttl_ = await r_ttl(request, f"vps_{vps_uuid}")
        if ttl_ > package_config["api_ip_vaild_min"]:
            await r_set(
                request,
                f'{package_config["package_name"]}_{vps_uuid}',
                await r_get(request, f"vps_{vps_uuid}"),
                await r_ttl(request, f"vps_{vps_uuid}"),
            )
    elif package_config["api_ip_vaild_max"]:

        ttl_ = await r_ttl(request, f"vps_{vps_uuid}")
        if ttl_ < package_config["api_ip_vaild_max"]:
            await r_set(
                request,
                f'{package_config["package_name"]}_{vps_uuid}',
                await r_get(request, f"vps_{vps_uuid}"),
                await r_ttl(request, f"vps_{vps_uuid}"),
            )
    else:

        await r_set(
            request,
            f'{package_config["package_name"]}_{vps_uuid}',
            await r_get(request, f"vps_{vps_uuid}"),
            await r_ttl(request, f"vps_{vps_uuid}"),
        )


@app.get("/manage_package", response_class=JSONResponse)
async def manage_package_(
    request: Request, username: str, password: str, package_name: str
):
    global RESPONSE_RESULT
    result = deepcopy(RESPONSE_RESULT)
    package = await auth_user(request, username, password)
    if isinstance(package_name, str):
        if package["private"]:
            for vps_uuid in await find_vps_by_packagename(request, package_name):
                await is_need_to_set_pool(request, package, vps_uuid)
            result["data"] = "finish"
        else:
            share_vpsuuid = set(await find_vps_by_share(request, False))
            all_vpsuuid = set(await r_keys(request, f"vps_*"))
            for vps_uuid in list(all_vpsuuid - share_vpsuuid):
                await is_need_to_set_pool(request, package, vps_uuid)
            result["data"] = "finish"
    else:
        result["state"] = 400
    return JSONResponse(result)


if __name__ == "__main__":
    uvicorn.run(app="api:app", host="127.0.0.1", port=8425, reload=True)
