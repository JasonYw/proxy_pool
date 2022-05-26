from fastapi import FastAPI, Query, Response, Path,Depends
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
from dia import consumer_dia

app = FastAPI()
abspath =os.path.abspath(__file__).replace(f'/{os.path.basename(__file__)}','')
config = configparser.ConfigParser()
config.read(f'{abspath}/conf.ini')
REDIS_HOST=config['REDIS']['REDIS_HOST']
REDIS_PORT=config['REDIS']['REDIS_PORT']
REDIS_DB =config['REDIS']['REDIS_DB']
REDIS_PASS=config['REDIS']['REDIS_PASS']
MYSQL_HOST=config['MYSQL']['MYSQL_HOST']
MYSQL_PORT=config['MYSQL']['MYSQL_PORT']
MYSQL_USER=config['MYSQL']['MYSQL_USER']
MYSQL_PASS=config['MYSQL']['MYSQL_PASS']
MYSQL_DB=config['MYSQL']['MYSQL_DB']


@app.on_event("startup")
async def startup_event():
    app.state.redis = await aioredis.create_redis(address=(REDIS_HOST, int(REDIS_PORT)), db=int(REDIS_DB), encoding="utf-8", password=REDIS_PASS)
    app.state.pool = await aiomysql.create_pool(host=MYSQL_HOST, port=int(MYSQL_PORT), user=MYSQL_USER, password=MYSQL_PASS, db=MYSQL_DB)
    # global SCHED
    # SCHED = BackgroundScheduler()
    # SCHED.add_job(consumer_dia,'interval', seconds=5,max_instances=1)
    # SCHED.start()


    

@app.on_event("shutdown")
async def shutdown_event():
    app.state.redis.close()
    await app.state.redis.wait_closed() 
    app.state.pool.close()
    # global SCHED
    # SCHED.shutdown()
    


async def ttl_(request,key_,min,max):
    ttl_ = await request.app.state.redis.get(key_)
    if ttl_ > min and ttl_ < max:
        return ttl_
    else:
        return False



def auth_expired_time(request,userdata):
    if isinstance(userdata.get('expired_time'),int):
        if userdata.get('expired_time') > int(time.time()):
            return True
        return False
    else:
        return True

async def auth_daily_count(request,username,userinfo,userdata):
    if userinfo[-1] == 'tunnel':
        if isinstance(userdata.get('now_day'),int):
            if userdata.get('now_day') < int(time.mktime(datetime.date.today().timetuple())):
                await request.app.state.redis.hset(
                    username,
                    'daily_rqs_count',userdata['tunnel_per_day'],
                    'now_day',int(time.mktime(datetime.date.today().timetuple()))
                )
                return True
            else:
                if userdata['daily_rqs_count']:
                    return True
            return False
        else:
            return True
    if userinfo[-1] == 'api':
        if isinstance(userdata['ip_per_day'],int):
            if int(userdata['ip_per_day']) > await request.app.state.redis.scard(f'{username}_{int(time.mktime(datetime.date.today().timetuple()))}'):
                return True
            return False
        else:
            return True




async def auth_user(request:Request,username:str,password:str):
    userdata = await request.app.state.redis.hgetall(username)
    userinfo = username.split('@')  #[username,packagename,id,api\tunnel]
    if userdata and (auth_expired_time(request,userdata) or await auth_daily_count(request,username,userinfo,userdata)):
        return await request.app.state.redis.hgetall(username)
    else:
        cur = await request.state.pool.cursor(aiomysql.DictCursor)
        await cur.execute(f'SELECT * FROM agent_userconfig WHERE username="{userinfo[0]}" AND password="{password}" LIMIT 1')
        userconfig = await cur.fetchone()
        await cur.execute(f'SELECT * FROM agent_package_user WHERE username="{userinfo[0]}" AND id={userinfo[2]} LIMIT 1')
        package_user = await cur.fetchone()
        await cur.execute(f'SELECT * FROM agent_packageconfig WHERE username="{userinfo[1]}" LIMIT 1')
        packageconfig = await cur.fetchone()
        await cur.close()
        if userconfig and package_user and packageconfig:
            if package_user.get(expired_time) != None:
                expired_time = time.mktime(package_user.get('expired_time').timetuple()) + 28800
                if expired_time > time.time():
                    await request.app.state.redis.hset(
                        username,
                        'expired_time',int(expired_time)
                    )
            else:
                await request.app.state.redis.hset(
                    username,
                    'password',password,
                )
                if userinfo[3] == 'api':
                    for i in ['ip_per_api_rqs','ip_per_day','ip_vaild_min','ip_vaild_max','ip_per_package']:
                        if packageconfig.get(i):
                            await request.app.state.redis.hset(
                                username,
                                i,packageconfig[i]
                            )
                    return await request.app.state.redis.hgetall(username)
                if userinfo[3] == 'tunnel':
                    for i in ['tunnel_per_day','tunnel_per_package']:
                        if packageconfig.get(i):
                            await request.app.state.redis.hset(
                                username,
                                i,packageconfig[i]
                            )
                        if i =='tunnel_per_day':
                            if packageconfig[i]:
                                await request.app.state.redis.hset(
                                    username,
                                    'daily_rqs_count',packageconfig[i],
                                    'now_day',int(time.mktime(datetime.date.today().timetuple()))
                                )
                    return await request.app.state.redis.hgetall(username)
    return None

        


@app.get("/get_ip",response_class=JSONResponse)
async def auth_(request:Request,username:str,password:str):
    package = await auth_user(request,username,password)
    if package:
        used_ip = set(await request.app.state.redis.smembers(f'{username}_{int(time.mktime(datetime.date.today().timetuple()))}'))
        keyslist = tuple(await request.app.state.redis.keys(f'{username.split("@")[1]}'))
        proxy_ips = set(await request.app.state.redus.megt(keyslist))
        if package.get('ip_per_api_rqs'):
            proxy_ips = list(proxy_ips - used_ip)[:package['ip_per_api_rqs']]
        else:
            return random.choice(list(proxy_ips - used_ip))


@app.get("/auth_for_vps")
async def auth_(request:Request,username:str,password:str,local_ip:str):
    package = await auth_user(request,username,password,local_ip)
    if package:
        userinfo = username.split('@')
        if userinfo[-1] == 'api':
            await request.app.state.redis.sadd(f'{username}_{int(time.mktime(datetime.date.today().timetuple()))}',local_ip)
            return 'ok'
        if userinfo[-1] == 'tunnel':
            await request.app.state.redis.hincrby(
                username,
                'daily_ip_count',-1
            )
            return 'ok'    
    return None


        
                


        





if __name__ == "__main__":
    uvicorn.run(app="api:app", host="127.0.0.1", port=8426, reload=True)


