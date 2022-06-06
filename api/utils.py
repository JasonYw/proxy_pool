from models import *
import datetime
import time


async def set_package_to_redis_by_mysql(request, packagename: str):
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


async def find_package_rule(request, package_name):
    packageconfig = await m_find_one(
        request,
        f'SELECT * FROM agent_packageconfig WHERE package_name = "{package_name}" LIMIT 1',
    )
    return packageconfig


async def find_vps_by_packagename(request, package_name):
    vpsuuid_list = []
    packageconfig = await m_find_all(
        request, f'SELECT * FROM agent_packagevps WHERE package_name = "{package_name}"'
    )
    for i in packageconfig:
        vpsuuid_list.append(i["vps_uuid"])
    return vpsuuid_list


async def find_vps_by_share(request, share: bool):
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


async def ttl_(request, key_, min, max):
    ttl_ = await r_ttl(request, key_)
    if ttl_ > min and ttl_ < max:
        return ttl_
    else:
        return False


async def set_package_to_redis_by_mysql(request, packagename: str):
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


async def set_user_record_to_redis_by_mysql(request, record_id):
    result = await m_find_one(
        request,
        f'SELECT * FROM agent_packageuser WHERE record_id="{record_id}" LIMIT 1',
    )
    if result:
        allcount = 0
        if result["expired_time"]:
            await r_sadd(request, record_id, f'expired_time&{result["expired_time"]}')
        result = await m_find_all(
            request,
            f'SELECT * FROM agent_api_userrecord WHERE record_id = "{record_id}"',
        )
        for i in result:
            await r_sadd(request, record_id, f"{i['day']}&api&{i['ip']}")
        result = await m_find_all(
            request,
            f'SELECT * FROM agent_tunnel_userrecord WHERE record_id = "{record_id}"',
        )
        for i in result:
            await r_sadd(request, record_id, f"{i['day']}&tunnel&{i['count']}")
            allcount += i["count"]
        await r_sadd(request, record_id, f"tunnelcount&{allcount}")
        return True
    else:
        return False


async def auth_username_password(request, record_id, username, password):
    result = False, False
    if await r_sismember(request, record_id, f"password&{password}"):
        result = True, False
        if await r_sismember(request, record_id, "is_superuser"):
            result = True, True
        else:
            result = True, False
    else:
        userconfig = await m_find_one(
            request,
            f'SELECT * FROM agent_userconfig WHERE username="{username}" LIMIT 1',
        )
        await r_srem(request, record_id, password)
        await r_sadd(request, record_id, f'password&{userconfig["password"]}')
        if userconfig["is_superuser"]:
            await r_sadd(request, record_id, "is_superuser")
        if password == userconfig["password"]:
            result = True, False
        if userconfig["is_superuser"]:
            result = True, True
    return result


def auth_expired_time(user_record, today):
    value = list(filter(lambda x: "expired_time&" in x, user_record))
    if not value:
        return True
    else:
        if int(value[0].replcae("expired_time&", "")) > today:
            return True
    return False


async def auth_tunnel_package(user_record, today, package):
    if isinstance(package.get("tunnel_per_day"), int):
        value = list(filter(lambda x: f"{today}&tunnel&" in x, user_record))
        if (
            value
            and value[0].replace(f"{today}&tunnel&", "") > package["tunnel_per_day"]
        ):
            return False
    if isinstance(package.get("tunnel_per_package"), int):
        value = list(filter(lambda x: "tunnelcount&" in x, user_record))
        if (
            value
            and value[0].replace("tunnelcount&", "") > package["tunnel_per_package"]
        ):
            return False
    return True


async def auth_api_package(user_record, today, package):
    if isinstance(package.get("ip_per_day"), int):
        value = list(filter(lambda x: f"{today}&api&" in x, user_record))
        if len(value) > package["ip_per_day"]:
            return False
    if isinstance(package.get("ip_per_package"), int):
        value = list(filter(lambda x: f"&api&" in x, user_record))
        if len(value) > package["ip_per_package"]:
            return False
    return True


async def auth_user(request, username: str, password: str):
    username, packagename, id_, kind = username.split(
        "&"
    )  # [username,packagename,id,api\tunnel]
    record_id = f"{username}&{packagename}&{id_}"
    packageconfig = await r_hgetall(packagename)
    user_record = await r_smembers(request, record_id)
    today = time.mktime(datetime.date.today().timetuple())
    if not packageconfig:
        right_package = await set_package_to_redis_by_mysql(request, packagename)
        packageconfig = await r_hgetall(packagename)
    if not user_record:
        right_record = await set_user_record_to_redis_by_mysql(request, record_id)
        user_record = await r_smembers(request, record_id)
    auth_, superuser = await auth_username_password(
        request, record_id, username, password
    )
    if auth_ and superuser:
        return True
    elif not auth_:
        return False
    elif auth_:
        if not right_package or not right_record:
            return False
        if not await auth_expired_time(user_record, today):
            return False
        if kind == "api":
            if not await auth_api_package(user_record, today, packageconfig):
                return False
        if kind == "tunnel":
            if not await auth_tunnel_package(user_record, today, packageconfig):
                return False
        return True
    else:
        return False
