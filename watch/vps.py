import paramiko
import requests
import time
import re
import os
import configparser
session = requests.session()
abspath =os.path.abspath(__file__).replace(f'/{os.path.basename(__file__)}','')
config = configparser.ConfigParser()
config.read(f'{abspath}/conf.ini')




PROXY_SERVICE_HOST =config['PROXY']['PROXY_SERVICE_HOST']
PROXY_SERVICE_PORT =config['PROXY']['PROXY_SERVICE_PORT']
PROXY_AGENT_HOST =config['PROXY']['PROXY_AGENT_HOST']
PROXY_AGENT_PORT =config['PROXY']['PROXY_AGENT_PORT']
PROXY_API_HOST =config['PROXY']['PROXY_API_HOST']
PROXY_API_PORT =config['PROXY']['PROXY_API_PORT']
VPS_PORT =config['PROXY']['VPS_PORT']
REDIS_HOST=config['REDIS']['REDIS_HOST']
REDIS_PORT=config['REDIS']['REDIS_PORT']
REDIS_DB =config['REDIS']['REDIS_DB']
REDIS_PASS=config['REDIS']['REDIS_PASS']
TUNNEL_NGINX_PORT =config['TUNNEL']['TUNNEL_NGINX_PORT']
TUNNEL_SQUID_HOST =config['TUNNEL']['TUNNEL_SQUID_HOST']
TUNNEL_SQUID_PORT =config['TUNNEL']['TUNNEL_SQUID_PORT']
TUNNEL_KEYS = config['TUNNEL']['TUNNEL_KEYS']

SQUID_AUTH_CONFIG =r'''
import sys
import json
import urllib.request
def matchpasswd(username, password, client_ip, local_ip):
    try:
        req = urllib.request.Request(url=f'http://{{PROXY_API_HOST}}:{{PROXY_API_PORT}}/auth_for_vps?username={username}&password={password}&client_ip={client_ip}', method='GET')
        res = json.loads(urllib.request.urlopen(req).read())
        if res:
            return True
        else:
            return False
    except:
        return False
if __name__ == '__main__':  
    while True:  
        line = sys.stdin.readline()  
        username, password, client_ip, local_ip = line.split()  
        if matchpasswd(username, password, client_ip, local_ip):  
            sys.stdout.write('OK\n')  
        else:  
            sys.stdout.write('ERR\n')  
        sys.stdout.flush()  
'''.replace('{{PROXY_API_HOST}}',PROXY_API_HOST).replace('{{PROXY_API_PORT}}',PROXY_API_PORT)




VPS_SQUID_CONFIG=r'''
acl localnet src 10.0.0.0/8
acl localnet src 172.16.0.0/12
acl localnet src 192.168.0.0/16
acl localnet src fc00::/7
acl localnet src fe80::/10
acl SSL_ports port 443
acl Safe_ports port 80
acl Safe_ports port 21
acl Safe_ports port 443
acl Safe_ports port 70
acl Safe_ports port 210
acl Safe_ports port 1025-65535
acl Safe_ports port 280
acl Safe_ports port 488
acl Safe_ports port 591
acl Safe_ports port 777
acl CONNECT method CONNECT
http_port {{VPS_PORT}}
auth_param basic program /usr/bin/python3 /etc/squid/squid_auth.py
auth_param basic key_extras "%>a %la"
auth_param basic credentialsttl 1 second
auth_param basic children 1000
auth_param basic casesensitive on
acl auth_users proxy_auth REQUIRED
http_access allow auth_users
http_access deny all
refresh_pattern ^ftp:  1440 20% 10080
refresh_pattern ^gopher: 1440 0% 1440
refresh_pattern -i (/cgi-bin/|\?) 0 0% 0
refresh_pattern .  0 20% 4320
visible_hostname proxy
'''.replace('{{VPS_PORT}}',VPS_PORT)

       
TUNNEL_NGINX_CONFIG=r'''
worker_processes  8;        
error_log /var/log/nginx/error.log warn;  
events {
    worker_connections 1024;
}
stream {
    log_format tcp_proxy '$remote_addr [$time_local] '
                         '$protocol $status $bytes_sent $bytes_received '
                         '$session_time "$upstream_addr" '
                         '"$upstream_bytes_sent" "$upstream_bytes_received" "$upstream_connect_time"';

    access_log /var/log/nginx/access.log tcp_proxy;
    open_log_file_cache off;
    limit_conn_zone $binary_remote_addr zone=addr:10m;
    upstream backend{
        server 127.0.0.3:1101;
        balancer_by_lua_block {
            local balancer = require "ngx.balancer"
            local host = ngx.ctx.proxy_host
            local port = ngx.ctx.proxy_port
            local ok, err = balancer.set_current_peer(host, port)
        }
    }
    server {
        preread_by_lua_block{
            local redis = require("resty.redis")
            local redis_instance = redis:new()
            local ok, err = redis_instance:connect("{{REDIS_HOST}}","{{REDIS_PORT}}")
            {{REDIS_PASS}}
            local res, err = redis_instance:select({{REDIS_DB}})
            local res, err = redis_instance:keys("{{TUNNEL_KEYS}}")
            local postion = math.random(#res)
            local proxy_ip,err = redis_instance:get(res[postion])
            ngx.ctx.proxy_host = string.match(proxy_ip,"%d+.%d+.%d+.%d+")
            ngx.ctx.proxy_port = string.sub(string.match(proxy_ip,":%d+"),2)
        }
        limit_conn addr 20;
        listen 127.0.0.1:{{TUNNEL_NGINX_PORT}};
        proxy_connect_timeout 3s;
        proxy_timeout 10s;
        proxy_download_rate 204800;
        proxy_pass backend;
    }
}
'''.replace('{{TUNNEL_KEYS}}',TUNNEL_KEYS).replace('{{REDIS_DB}}',REDIS_DB).replace('{{TUNNEL_NGINX_PORT}}',TUNNEL_NGINX_PORT).replace('{{REDIS_HOST}}',REDIS_HOST).replace('{{REDIS_PORT}}',REDIS_PORT)

if REDIS_PASS:
    TUNNEL_NGINX_CONFIG=TUNNEL_NGINX_CONFIG.replace('{{REDIS_PASS}}',f'local res, err = redis_instance:auth("{REDIS_PASS}")')
else:
    TUNNEL_NGINX_CONFIG=TUNNEL_NGINX_CONFIG.replace('{{REDIS_PASS}}','')



TUUNEL_SQUID_CONFIG =r'''
acl localnet src 10.0.0.0/8
acl localnet src 172.16.0.0/12
acl localnet src 192.168.0.0/16
acl localnet src fc00::/7
acl localnet src fe80::/10
acl SSL_ports port 443
acl Safe_ports port 80
acl Safe_ports port 21
acl Safe_ports port 443
acl Safe_ports port 70
acl Safe_ports port 210
acl Safe_ports port 1025-65535
acl Safe_ports port 280
acl Safe_ports port 488
acl Safe_ports port 591
acl Safe_ports port 777
acl CONNECT method CONNECT
http_port {{TUNNEL_SQUID_PORT}}
auth_param basic program /usr/bin/python3 /etc/squid/squid_auth.py
auth_param basic key_extras "%>a %la"
auth_param basic credentialsttl 1 second
auth_param basic children 1000
auth_param basic casesensitive on
acl auth_users proxy_auth REQUIRED
http_access allow auth_users
http_access deny all
cache_peer 127.0.0.1 parent {{TUNNEL_NGINX_PORT}} 0 no-query proxy-only
refresh_pattern ^ftp:  1440 20% 10080
refresh_pattern ^gopher: 1440 0% 1440
refresh_pattern -i (/cgi-bin/|\?) 0 0% 0
refresh_pattern .  0 20% 4320
visible_hostname proxy
'''.replace('{{TUNNEL_SQUID_PORT}}',TUNNEL_SQUID_PORT).replace('{{TUNNEL_NGINX_PORT}}',TUNNEL_NGINX_PORT)




class VpsService:
    '''
        封装通过ssh协议，控制拨号机的方法
        vps_id为拨号机的配置信息
    '''
    def __init__(self,vps_conf) -> None:
        '''
            vps_id 拨号机id
        '''
        self.ssh = None
        self.vps_conf = vps_conf
        self.connect()
        
        
  
    def __exit__(self,exc_type, exc_val, exc_tb):
        self.close()
        
        
    def __enter__(self):
        return self

    
    def close(self):
        try:
            self.ssh.close()
        except:
            pass

    
    
    def connect(self):
        '''
            hostname:主机ip，或者主机名
            port：登陆端口
            username：用户
            password：密码
            通过ssh进行连接，登录拨号机
            
        '''
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname=self.vps_config["host"], port=self.vps_config["port"], username=self.vps_config["user"], password=self.vps_config["password"]
        )
        

    def deployment(self) -> bool:
        if self.ssh:
            cmd_list =[
                'yum install python36 -y',
                'yum install squid -y',
                'rm -f /etc/squid/squid.conf',
                'rm -f /etc/squid/squid_auth.py'
            ]
            for cmd_ in cmd_list:
                self.ssh.exec_command(cmd_)
            sftp = self.ssh.open_sftp()
            fileObject = sftp.open('/etc/squid/squid.conf','w')
            fileObject.write(VPS_SQUID_CONFIG)
            fileObject.close()
            fileObject = sftp.open('/etc/squid/squid_auth.py','w')
            fileObject.write(SQUID_AUTH_CONFIG)
            fileObject.close()
            self.ssh.exec_command('systemctl stop squid')
            self.ssh.exec_command('systemctl start squid')
            self.close()
        else:
            raise ValueError('ssh 无法建立连接')

    
    def dia(self):
        '''
            负责拨号，将获取到的ip返回
        '''
        if self.ssh:
            while True:
                self.ssh.exec_command("pppoe-stop")
                time.sleep(5)
                self.ssh.exec_command("pppoe-start")
                # logger.info(f'{self.vps["owner"]}_{self.vps["id"]} pppoe-stop;pppoe-start')
                time.sleep(5)
                while True:
                    time.sleep(5)
                    try:
                        stdin, stdout, stderr = self.ssh.exec_command("pppoe-status")
                        stdin.flush()
                        # logger.info(f'{self.vps["owner"]}_{self.vps["id"]} pppoe-status')
                        time.sleep(5)
                    except Exception as e:
                        # logger.error(f'{self.vps["owner"]}_{self.vps["id"]}:{e}')
                        return None
                    res, err = stdout.read().decode('utf-8'), stderr.read().decode('utf-8')
                    result = res if res else err
                    if "Link is down" in res:
                        continue
                    break
                pppoe_ip = re.findall(r"inet.(\d+.\d+.\d+.\d+)", result)
                if pppoe_ip:
                    self.close()
                    # logger.info(f'{self.vps["owner"]}_{self.vps["id"]} 关闭ssh连接')
                    # logger.info(f'{self.vps["owner"]}_{self.vps["id"]} 获取到 {pppoe_ip[0]}')
                    return pppoe_ip[0]
                continue
    
    def watch(self):
        self.mem_info()
        self.cpu_info()
        self.ionetwork()
        self.close()
        return {
            'MemTotal':self.MemTotal,
            'MemFree':self.MemFree,
            'MemAvailable':self.MemAvailable,
            'cpu_user':self.cpu_user,
            'cpu_sys':self.cpu_sys,
            'cpu_idle':self.cpu_idle,
            'eth0_Receive':self.eth0_Receive,
            'eth0_Transmit':self.eth0_Transmit
        }
    

    def mem_info(self):
        '''
            MemTotal 总量
            MemFree 可用
            MemAvailable 剩余
        '''
        if self.ssh:
            stdout = self.ssh.exec_command("cat /proc/meminfo",)[1]
            self.MemTotal,self.MemFree,self.MemAvailable = re.findall(r'MemTotal.\s+(\d+)\skB\nMemFree.\s+(\d+)\skB\nMemAvailable.\s+(\d+)\skB\n',stdout.read().decode('utf-8'))[0]
            
    def cpu_info(self):
        '''
            vmstat 1 1 | tail -n 1 的返回值按照顺序排序
            us: 用户进程执行消耗cpu时间(user time)
            sy: 系统进程消耗cpu时间(system time)
            id: 空闲时间(包括IO等待时间)
            # CPU% = 1 – idleTime / sysTime * 100      
        '''
        if self.ssh:
            stdout = self.ssh.exec_command("vmstat 1 1 | tail -n 1", )[1]
            #用户空间上进程运行的时间百分比,内核空间上进程运行的时间百分比,闲置时间百分比
            self.cpu_user,self.cpu_sys,self.cpu_idle =stdout.readlines()[0].split()[12:15] 
           
    def ionetwork(self):
        if self.ssh:
            stdout = self.ssh.exec_command("cat /proc/net/dev", )[1]
            eth0 =re.findall(r'(\d+)',stdout.read().decode('utf-8').split('\n')[4].replace('eth0',''))
            self.eth0_Receive = eth0[0]
            self.eth0_Transmit = eth0[8]
           
       



    


if  __name__ =="__main__":
    a = VpsService('a')
    a.ionetwork()