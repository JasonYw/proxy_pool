import requests
from mail import send_mail
import time



def control_dia(vps_conf,need_sleep):
    '''
        vps 拨号服务器配置
        need_sleep 是否需要睡眠
        消费者
    '''    
    key = f'proxy_{vps_conf["vps_uuid"]}'
    redis_ = get_redis_connection()
    ttl_ = redis_.ttl(key)
    if vps_conf['expiredat']:
        if not vps_conf['env_is_ok']:
            pass
        if ttl_ < 30 and ttl_ != -2 and ttl_ != -1:
            if len(redis_.keys('proxy_')) < 2:
                redis_.set_(key,redis_.get_(key),120)
                # logger.info(f'{key} 代理有效期重置为120秒')
            else:
                if need_sleep:
                    redis_.del_(key)
                    time.sleep(10)
                while True:
                    with VpsService(vps_conf["vps_uuid"]) as service_:
                        ip_ = service_.dia()
                        if ip_ and verify_vps_ip(ip_):
                            redis_.set_(key,f'{ip_}:{settings.PROXY_PORT}',vps_conf['dia_frequency'])
                            # logger.info(f'{vps} 获取到 {ip_} 已经放入redis')
                            # rewrite_config()
                            # logger.info(f'{vps} 重新加载配置完毕')
                            return
                        else:
                            continue
    return


def package_thread(threading_group,vps_conf,need_sleep):
    '''
        threading_group 线程组，防止同一台拨号机同时给出拨号命令
        vps 拨号服务器配置
        need_sleep 是否需要睡眠
    '''
    if not threading_group.get(vps_conf['vps_uuid']):
        threading_group[vps_conf['vps_uuid']] = Thread(name=vps_conf['vps_uuid'],target=control_dia,args=(vps_conf,need_sleep))
        threading_group[vps_conf['vps_uuid']].start()
        # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
    else:
        if not threading_group[vps_conf['vps_uuid']].isAlive():
            threading_group[vps_conf['vps_uuid']] = Thread(name=vps_conf['vps_uuid'],target=control_dia,args=(vps_conf,need_sleep))
            threading_group[vps_conf['vps_uuid']].start()
            # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
        else:
            pass
    return


def func_run():
    # logger.info(f'代理服务开始')
    threading_group = {}
    while True:
        # try:
        all_vps_config = VpsConfig.objects.values_list('vps_uuid','dia_frequency','env_is_ok','expiredat')
        # print(all_vps_config)
        # time.sleep(100)
        if not all_vps_config:
            print('目前无vps拨号机')
            time.sleep(60*60*5)
        for vps_conf in all_vps_config:
            package_thread(threading_group,vps_conf,True)
        # except Exception as e:
        #     send_mail(f'拨号调度出现问题',e)
        #     continue



# def get_all_vpsuuid(request):
#     results = {'status':404,'data':[]}
#     if request.method == 'POST':
#         username = request.GET.get('username',default=None)
#         password = request.GET.get('password',default=None)
#         if auth_(username,password):
#             results['status'] = 200
#             results['data'] = VpsOwner.objects.filter(username=username).values_list('vps_uuid',flat=True)
#     return JsonResponse(results)




# def test_vps(request):
#     if request.method == 'GET':
#         vps_uuid = request.GET.get('vps_uuid',default=None)
#         vps_ = VpsService(vps_uuid)
#         if vps_.ping():
#             messages.add_message(request, messages.SUCCESS, f'{vps_uuid} 服务器正常')
#         else:
#             messages.add_message(request,messages.ERROR,f'{vps_uuid} 服务器异常')
#     return redirect('/admin/managevpsweb/vpsconfig/') 
#     # return render(request,'test_vps.html',locals())



def consumer_(vps_uuid):
    conf = VpsConfig.objects.filter(vps_uuid=vps_uuid).first()
    vps_ = VpsService()
    vps_.ping()
    # if not conf.is_deploment:
    #     vps_.deployment()





def package_thread(threading_group,vps_uuiid):
    '''
        threading_group 线程组，防止同一台拨号机同时给出拨号命令
        vps 拨号服务器配置
        need_sleep 是否需要睡眠
    '''
    if not threading_group.get(vps_uuiid):
        threading_group[vps_uuiid] = Thread(name=vps_uuiid,target=consumer_,args=(vps_uuiid,))
        threading_group[vps_uuiid].start()
        # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
    else:
        if not threading_group[vps_uuiid].isAlive():
            threading_group[vps_uuiid] = Thread(name=vps_uuiid,target=consumer_,args=(vps_uuiid,))
            threading_group[vps_uuiid].start()
            # logger.info(f'{vps["owner"]}_{vps["id"]} 开始拨号')
        else:
            pass
    return


def func_run():
    threading_group = {}
    while True:
        all_vps_config = VpsConfig.objects.values_list('vps_uuid')
        if not all_vps_config:
            time.sleep(300)
        for vps_uuid in all_vps_config:
            package_thread(threading_group,vps_uuid)
        time.sleep(300)





