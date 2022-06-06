async def r_smembers(request, key):
    return await request.app.state.smembers(key)


async def r_srem(request, key, value):
    return await request.app.state.srem(key, value)


async def r_sismember(request, key, value):
    return await request.app.state.sismember(key, value)


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
