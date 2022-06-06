from fastapi import FastAPI, Query, Response, Path, Depends
from fastapi.responses import JSONResponse
from fastapi import Request
import random
import uvicorn
import aioredis
import aiomysql
import os
import configparser
from apscheduler.schedulers.background import BackgroundScheduler
from copy import deepcopy
from models import *
from utils import *

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


# @app.get("/auth_for_vps", response_class=JSONResponse)
# async def auth_(request: Request, username: str, password: str):
#     global RESPONSE_RESULT
#     result = deepcopy(RESPONSE_RESULT)
#     if not await auth_user(request, username, password):
#         result["data"] = "验证失败"
#         result["state"] = 400
#     else:
#         username, packagename, id_, kind = username.split("&")  # [username,packagename,id,api\tunnel]
#         record_id = f'{username}&{packagename}&{id_}'
#         today = time.mktime(datetime.date.today().timetuple())
#         if '&api' in username:
#             await r_sadd(request,record_id,f"{today}&api&{request.client.host}")
#         if '&tunnel' in username:
#             # await r_sadd(request,record_id,f"{today}&tunnel&{}")
#             # await r_sadd(request,record_id,f'tunnelcount&{allcount}')
#         result["data"] = "验证成功"
#     return JSONResponse(result)


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
        await set_package_to_redis_by_mysql(request, package_name)
    else:
        result["state"] = 400
    return JSONResponse(result)


if __name__ == "__main__":
    uvicorn.run(app="api:app", host="127.0.0.1", port=8425, reload=True)
