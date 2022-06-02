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


async def r_hset(request, key, value):
    return await request.app.state.redis.hset(key, *value)


async def r_exists(request, key):
    return await request.app.state.redis.r_exists(key)


async def r_hgetall(request, key):
    return await request.app.state.redis.hgetall(key)


async def r_get(request, key):
    return await request.app.state.redis.get(key)


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


def auth_expired_time(request, userdata):
    if isinstance(userdata.get("expired_time"), int):
        if userdata.get("expired_time") > int(time.time()):
            return True
        return False
    else:
        return True


async def auth_daily_count(request, username, userinfo, userdata):
    time.mktime(datetime.date.today().timetuple())
    if userinfo[-1] == "tunnel":
        if isinstance(userdata.get("now_day"), int):
            if userdata.get("now_day") < int(
                time.mktime(datetime.date.today().timetuple())
            ):
                await request.app.state.redis.hset(
                    username,
                    "daily_rqs_count",
                    userdata["tunnel_per_day"],
                    "now_day",
                    int(time.mktime(datetime.date.today().timetuple())),
                )
                return True
            else:
                if userdata["daily_rqs_count"]:
                    return True
            return False
        else:
            return True
    if userinfo[-1] == "api":
        if isinstance(userdata["ip_per_day"], int):
            if int(userdata["ip_per_day"]) > await request.app.state.redis.scard(
                f"{username}_{int(time.mktime(datetime.date.today().timetuple()))}"
            ):
                return True
            return False
        else:
            return True


async def auth_by_redis(request: Request, username, password, userinfo):
    userdata = await request.app.state.redis.hgetall(username)
    if userdata and (
        auth_expired_time(request, userdata)
        or await auth_daily_count(request, username, userinfo, userdata)
    ):
        return await request.app.state.redis.hgetall(username)
    else:
        return False


async def auth_by_mysql(request: Request, userinfo, password: str):
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    await cur.execute(
        f'SELECT * FROM agent_package_user WHERE username="{userinfo[0]}" AND id={userinfo[2]} LIMIT 1'
    )
    package_user = await cur.fetchone()
    await cur.execute(
        f'SELECT * FROM agent_packageconfig WHERE username="{userinfo[1]}" LIMIT 1'
    )
    packageconfig = await cur.fetchone()
    await cur.close()
    return package_user, packageconfig


async def auth_username_password(request, username, password):
    if request.app.state.redis.get(username) == password:
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


"""
ip_per_api_rqs
ip_per_day
ip_per_package
tunnel_per_day
tunnel_per_package
private
create_time
package_name
api_duplicate_time

"""


async def auth_api_package_byredis(request, username, packagename, id):
    today = time.mktime(datetime.date.today().timetuple())
    daily_key = f"{username}&{packagename}&{id}&{today}"
    package_key = f"{username}&{packagename}&{id}"
    package = await r_hgetall(packagename)
    rule = {"ip_per_day": daily_key, "ip_per_package": package_key}
    if package:
        for i, j in rule.items():
            if isinstance(package.get(i), int):
                if r_exists(request, j):
                    if await r_scard(request, j) > package[i]:
                        return False
                else:
                    result = await m_find_all(
                        request,
                        f'SELECT * FROM agent_userrecord WHERE user_package_id ="{j}"',
                    )
                    if result:
                        for i in result:
                            r_sadd(j, i["ip"])
                        if len(result) > package[i]:
                            return False
    else:
        result = await m_find_one(
            f'SELECT * FROM agent_packageconfig WHERE package_name ="{packagename}" LIMIT 1'
        )
        if not result:
            return False
        else:
            config = []
            for i, j in result.items():
                config.append(i)
                config.append(j)
            await r_hset(request, packagename, tuple(config))
            return await auth_api_package_byredis(request, username, packagename, id)
    return True


async def auth_user(request: Request, username: str, password: str):
    userinfo = username.split("&")  # [username,packagename,id,api\tunnel]


@app.get("/auth_for_vps", response_class=JSONResponse)
async def auth_(request: Request, username: str, password: str, local_ip: str):
    global RESPONSE_RESULT
    result = deepcopy(RESPONSE_RESULT)
    pass


"""
    用户提取代理api
"""


async def ttl_(request, key_, min, max):
    ttl_ = await request.app.state.redis.get(key_)
    if ttl_ > min and ttl_ < max:
        return ttl_
    else:
        return False


@app.get("/get_ip", response_class=JSONResponse)
async def auth_(request: Request, username: str, password: str):
    global RESPONSE_RESULT
    result = deepcopy(RESPONSE_RESULT)
    package = await auth_user(request, username, password)
    if package:
        used_ip = set(
            await request.app.state.redis.smembers(
                f"{username}_{int(time.mktime(datetime.date.today().timetuple()))}"
            )
        )
        keyslist = tuple(
            await request.app.state.redis.keys(f'{username.split("&")[1]}')
        )
        proxy_ips = set(await request.app.state.redus.megt(keyslist))
        if package.get("ip_per_api_rqs"):
            result["data"] = list(proxy_ips - used_ip)[: package["ip_per_api_rqs"]]
        else:
            result["data"] = [random.choice(list(proxy_ips - used_ip))]
    return JSONResponse(result)


"""
    处理监听套餐变化
"""


async def find_package_rule(request: Request, package_name):
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    await cur.execute(
        f'SELECT * FROM agent_packageconfig WHERE package_name = "{package_name}" LIMIT 1'
    )
    packageconfig = await cur.fetchone()
    await cur.close()
    return packageconfig


async def find_vps_by_packagename(request: Request, package_name):
    vpsuuid_list = []
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    await cur.execute(
        f'SELECT * FROM agent_package_vps WHERE package_name = "{package_name}"'
    )
    packageconfig = await cur.fetchall()
    await cur.close()
    for i in packageconfig:
        vpsuuid_list.append(i["vps_uuid"])
    return vpsuuid_list


async def find_vps_by_share(request: Request, share: bool):
    vpsuuid_list = []
    cur = await request.state.pool.cursor(aiomysql.DictCursor)
    if share:
        await cur.execute(f"SELECT * FROM agent_vpsconfig WHERE share")
    else:
        await cur.execute(f"SELECT * FROM agent_vpsconfig WHERE NOT share")
    vpsconfig = await cur.fetchall()
    await cur.close()
    for i in vpsconfig:
        vpsuuid_list.append(i["vps_uuid"])
    return vpsuuid_list


async def is_need_to_set_pool(request, package_config, vps_uuid):
    if package_config["api_ip_vaild_min"] or package_config["api_ip_vaild_max"]:

        ttl_ = await request.app.state.redis.ttl(f"vps_{vps_uuid}")
        if (
            ttl_ > package_config["api_ip_vaild_min"]
            and ttl_ < package_config["api_ip_vaild_max"]
        ):
            await request.app.state.redis.set(
                f'{package_config["package_name"]}_{vps_uuid}',
                await request.app.state.redis.get(f"vps_{vps_uuid}"),
                await request.app.state.redis.ttl(f"vps_{vps_uuid}"),
            )
    elif package_config["api_ip_vaild_min"]:

        ttl_ = await request.app.state.redis.ttl(f"vps_{vps_uuid}")
        if ttl_ > package_config["api_ip_vaild_min"]:
            await request.app.state.redis.set(
                f'{package_config["package_name"]}_{vps_uuid}',
                await request.app.state.redis.get(f"vps_{vps_uuid}"),
                await request.app.state.redis.ttl(f"vps_{vps_uuid}"),
            )
    elif package_config["api_ip_vaild_max"]:

        ttl_ = await request.app.state.redis.ttl(f"vps_{vps_uuid}")
        if ttl_ < package_config["api_ip_vaild_max"]:
            await request.app.state.redis.set(
                f'{package_config["package_name"]}_{vps_uuid}',
                await request.app.state.redis.get(f"vps_{vps_uuid}"),
                await request.app.state.redis.ttl(f"vps_{vps_uuid}"),
            )
    else:

        await request.app.state.redis.set(
            f'{package_config["package_name"]}_{vps_uuid}',
            await request.app.state.redis.get(f"vps_{vps_uuid}"),
            await request.app.state.redis.ttl(f"vps_{vps_uuid}"),
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
            all_vpsuuid = set(await request.app.state.redis.keys(f"vps_*"))
            for vps_uuid in list(all_vpsuuid - share_vpsuuid):
                await is_need_to_set_pool(request, package, vps_uuid)
            result["data"] = "finish"
    else:
        result["state"] = 400
    return JSONResponse(result)


if __name__ == "__main__":
    uvicorn.run(app="api:app", host="127.0.0.1", port=8425, reload=True)
