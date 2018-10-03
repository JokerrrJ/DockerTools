# -*- coding: utf-8 -*-

import etcd,docker,json,time
import optparse,os,sys
from docker import errors

if sys.getdefaultencoding() != 'utf-8':
    reload(sys)
    sys.setdefaultencoding('utf-8')

def read_hosts():
    if not os.path.exists('hosts_config'):
        print("hosts_config is not exist.")
        exit()
    f=open('./hosts_config','r')
    tmp = []
    for n in f.readlines():
        tmp.append(n.strip('\n').split(' '))
    f.close()
    extra_hosts = {value:key for key,value in dict(tmp).items()}
    return extra_hosts

def read_hostname(Address):
    extra_hosts = read_hosts()
    extra_hosts = {value: key for key, value in extra_hosts.items()}
    return extra_hosts.get(Address)

def docker_images(Image):
    res = docker_client.images(name=Image)
    return res

def docker_create_container_volume(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Docker_image):
    try:
        if not Docker_image:
            raise docker.errors.NotFound(111,11,11)
        if not Volume:
            Volume = Container_bind = Host_bind = None
            dict = docker_create_container(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Binds=None)
        else:
            Volume = Volume.split(':')
            Host_bind = Volume[0]
            Container_bind = Volume[1]
            Binds = {Volume[0]: {'bind': Volume[1], 'mode': 'rw'}}
            dict = docker_create_container(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Binds)

    except docker.errors.NotFound:
        print("No such image: %s"%(Image))
        exit()
    except docker.errors.APIError:
        print("The container name '%s' is already in use by container"%(Name))
        exit()
    Container_id = dict['Id']
    docker_start_container(Container_id)
    docker_create_network(Container_id, Bridge, Address, Gateway)
    value = {
        'Image': Image,
        'Name': Name,
        'Bridge': Bridge,
        'Address': Address,
        'Gateway': Gateway,
        'Host_bind': Host_bind,
        'Container_bind': Container_bind,
        'Memory': Memory,
        'Cpu': Cpu,
        'Hostname':Hostname
    }
    value = json.dumps(value)
    set_etcd_info(Container_id, value)
    docker_list_container(Container_id)

def docker_create_container_type_cpu(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu):
    Hostname = read_hostname(Address)
    Docker_image = docker_images(Image)
    if not Cpu:
        print(type(Cpu))
        docker_create_container_volume(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Docker_image)
    else:
        Cpu = int(Cpu)
        print(type(Cpu))
        docker_create_container_volume(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Docker_image)

def docker_create_container(Image,Volume,Name,Bridge,Address,Gateway,Memory,Cpu,Hostname,Binds):
    dict = docker_client.create_container(image=Image, user='root', command='/root/pi.sh',
                                          host_config=docker_client.create_host_config(mem_limit=Memory,
                                                                                       cpu_shares=Cpu,
                                                                                       network_mode='none',
                                                                                       privileged=True, binds=Binds,
                                                                                       extra_hosts=read_hosts()),
                                          name=Name, hostname=Hostname)
    return dict

def docker_remove_container(Name):
    try:
        container_info = docker_client.inspect_container(resource_id=Name)
        pid = str(container_info['State']['Pid'])
        Container_id = str(container_info['Id'])
        os.system('rm -rf /var/run/netns/%s' % (pid))
        docker_client.remove_container(container=Name,force=True)
        delete_etcd_info(Container_id)
    except docker.errors.NotFound:
        print("No such container name: %s"%(Name))
        exit()

def docker_start_container(Container_id):
    docker_client.start(container=Container_id)

def docker_restart_container(Name):
    try:
        container_info = docker_client.inspect_container(resource_id=Name)
        Container_id = str(container_info['Id'])
        docker_client.start(container=Container_id)
        value = get_etcd_info(Container_id)
        value = json.loads(value)
        docker_create_network(Container_id, value['Bridge'], value['Address'], value['Gateway'])
        docker_list_container(Container_id)
    except docker.errors.NotFound:
        print("No such container name: %s" % (Name))
        exit()

def docker_stop_container(Name):
    try:
        container_info = docker_client.inspect_container(resource_id=Name)
        pid = str(container_info['State']['Pid'])
        Container_id = str(container_info['Id'])
        print(Container_id)
        os.system('rm -rf /var/run/netns/%s' %(pid))
        docker_client.stop(container=Name)
    except docker.errors.NotFound:
        print("No such container name: %s" % (Name))
        exit()

def docker_create_network(Container_id, Bridge, Address, Gateway):
    try:
        container_info = docker_client.inspect_container(resource_id=Container_id)
        pid = str(container_info['State']['Pid'])
    except:
        pid = 0
    if int(pid) != 0:
        if not os.path.exists('/var/run/netns'):
            os.makedirs('/var/run/netns')
        source_namespace = '/proc/' + pid + '/ns/net'
        destination_namespace = '/var/run/netns/' + pid
        if not os.path.exists(destination_namespace):
            link = 'ln -s %s %s' % (source_namespace, destination_namespace)
            os.system(link)
            os.system('ip link add tap%s type veth peer name veth%s 2>> /var/log/docker.log' % (pid, pid))
            os.system('brctl addif %s tap%s 2>> /var/log/docker.log' % (Bridge, pid))
            os.system('ip link set dev tap%s up 2>> /var/log/docker.log' % pid)
            os.system('ip link set veth%s netns %s 2>> /var/log/docker.log' % (pid, pid))
            os.system(
                'ip netns exec %s ip link set dev veth%s name eth0 2>> /var/log/docker.log' % (pid, pid))
            os.system('ip netns exec %s ip link set eth0 up 2>> /var/log/docker.log' % pid)
            os.system('ip netns exec %s ip addr add %s/24 dev eth0 2>> /var/log/docker.log' % (pid, Address))
            os.system('ip netns exec %s ip route add default via %s 2>> /var/log/docker.log' % (pid, Gateway))

def docker_list_container(Container_id):
    if Container_id:
        res = docker_client.containers(filters={'id':Container_id})
        print(res)
    else:
        res = docker_client.containers(all=True)
        for n in res:
            print(n)
            print("\n".strip())

def get_etcd_info(Container_id):
    res = etcd_client.get(Container_id)
    return res.value

def set_etcd_info(Container_id,value):
    etcd_client.set(Container_id,value)

def list_etcd_into():
    res = etcd_client.get('/')
    for n in res._children:
        print(n)
        print("\n".strip())

def delete_etcd_info(Container_id):
    etcd_client.delete(Container_id)

def Options_parameters():
    parse = optparse.OptionParser(usage='"python %prog arg1 [options]"')
    parse.add_option('-n', dest='name', action='store', type=str, metavar='container', help='容器名称')
    group = optparse.OptionGroup(parse, "create_container", "创建容器。当arg1为create_container,可以使用以下参数。")
    group.add_option('-i', dest='image', action='store', type=str, metavar='image', help='镜像名称')
    group.add_option('-a', dest='address', action='store', type=str, metavar='address', help='容器ip地址')
    group.add_option('-g', dest='gateway', action='store', type=str, metavar='gateway', help='容器网关地址')
    group.add_option('-b', dest='bridge', action='store', type=str, metavar='bridge', help='网桥名称')
    group.add_option('-v', dest='volume', action='store', type=str, metavar='volume', default=None, help='宿主机挂载路径:容器挂载路径')
    group.add_option('-m', dest='memory', action='store', type=str, metavar='memory', default=None, help='内存限制')
    group.add_option('-c', dest='cpu', action='store', type=str, metavar='cpu', default=None, help='cup权重比例')
    parse.add_option_group(group)
    group = optparse.OptionGroup(parse, "stop_container", "停止指定容器。")
    parse.add_option_group(group)
    group = optparse.OptionGroup(parse, "start_container", "启动指定容器。")
    parse.add_option_group(group)
    group = optparse.OptionGroup(parse, "container_status", "列出所有容器状态。")
    parse.add_option_group(group)
    group = optparse.OptionGroup(parse, "container_info", "列出所有容器信息。")
    parse.add_option_group(group)
    group = optparse.OptionGroup(parse, "remove_container", "移除指定容器。")
    parse.add_option_group(group)
    options, args = parse.parse_args()
    if len(args) != 1:
        parse.error('"usage:python %s arg1 [options]"' % os.path.basename(sys.argv[0]))
    if args[0] == 'create_container':
        if not options.address:
            parse.error('缺少 -a 或者 -address 选项参数')
        elif not options.image:
            parse.error('缺少 -i 或者 --image 选项参数')
        elif not options.gateway:
            parse.error('缺少 -g 或者 -gateway 选项参数')
        elif not options.name:
            parse.error('缺少 -n 或者 --name 选项参数')
        elif not options.bridge:
            parse.error('缺少 -b 或者 --bridge 选项参数')
        else:
            docker_create_container_type_cpu(options.image,options.volume,options.name,options.bridge,options.address,options.gateway,options.memory,options.cpu)
    elif args[0] == 'stop_container':
        if not options.name:
            parse.error('缺少 -n 或者 --name 选项参数')
        else:
            docker_stop_container(options.name)
    elif args[0] == 'start_container':
        if not options.name:
            parse.error('缺少 -n 或者 --name 选项参数')
        else:
            docker_restart_container(options.name)
    elif args[0] == 'container_status':
        Container_id = None
        docker_list_container(Container_id)
    elif args[0] == 'container_info':
        list_etcd_into()
    elif args[0] == 'remove_container':
        if not options.name:
            parse.error('缺少 -n 或者 --name 选项参数')
        else:
            docker_remove_container(options.name)
    else:
        parse.error('args1 输入错误')

if __name__ == '__main__':
    try:
        docker_client = docker.Client(base_url='unix:///var/run/docker.sock', version='1.19', timeout=120)
        etcd_client = etcd.Client(host='172.16.200.111', port=2379)
    except:
        print("The connection has disconnected. Please check docker or etcd.")
        exit()
    Options_parameters()
