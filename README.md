# DockerTools
python里etcd的安装方法:                                                                                                             
安装基础库                                                                                                                           
yum install libffi libffi-devel python-devel                                                                                       
安装程序                                                                                                                            
git clone https://github.com/jplana/python-etcd.git                                                                                
cd python-etcd                                                                                                                     
python setup.py install                                                                                                            
                                                                                                                                          
python里docker的安装方法:                                                                                                                  
easy_install docker-py                                                                                                                   

hosts_config文件hosts填写格式：                                                                                                           
172.16.200.111:data1                                                                                                                      
172.16.200.112:data2                                                                                                                      
                                                                                                                                          
使用方式：                                                                                                                                 
python Docker.py -h                                                                                                                       
