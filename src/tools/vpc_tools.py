# coding: utf-8
import os
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkvpc.v2.region.vpc_region import VpcRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkvpc.v2 import *
from dotenv import load_dotenv
from typing import List, Optional, Dict
from mcp.server.fastmcp import FastMCP
import os
import logging
load_dotenv()  # 这将默认从当前目录下的 .env 文件加载变量
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 配置华为云认证信息
def get_credentials():
    # 从环境变量获取AK/SK，或者直接写在这里（不推荐）
    ak = os.getenv("HUAWEI_CLOUD_AK")
    sk = os.getenv("HUAWEI_CLOUD_SK")
    project_id = os.getenv("HUAWEI_REGION_CN_GUANGZHOU_PROJECT_ID")  # 项目ID
    
    if not all([ak, sk,project_id]):
        raise ValueError("请设置环境变量: HUAWEI_CLOUD_AK, HUAWEI_CLOUD_SK, HUAWEI_CLOUD_PROJECT_ID")
    
    return BasicCredentials(ak, sk,project_id)


#创建vpc客户端
def get_vpc_client(regin="cn-south-1"):
    credentials = get_credentials()

    return VpcClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(VpcRegion.value_of(regin)) \
        .build()

# 获取vpcid
def get_vpc_id(target_vpc_name=None):
    """
    获取VPC ID，如果target_vpc_name为None，则打印所有VPC及其ID。
    :param client: 已认证的VpcClient对象
    :param target_vpc_name: 目标VPC名称（可选）
    :return: 找到的目标VPC的ID或None
    """
    try:
        client=get_vpc_client()
        # 创建ListVpcsRequest请求
        request = ListVpcsRequest()
        # 发送请求，获取响应
        response = client.list_vpcs(request)

        # 解析响应，查找目标VPC ID
        for vpc in response.vpcs:
            if target_vpc_name is None:
                print(f"VPC Name: {vpc.name}, VPC ID: {vpc.id}")
            elif vpc.name == target_vpc_name:
                return vpc.id
        
        # 如果没有找到目标VPC且提供了target_vpc_name，则返回None
        if target_vpc_name is not None:
            print(f"未找到名为{target_vpc_name}的VPC")
            return None
    except exceptions.ClientRequestException as e:
        print(e.status_code)
        print(e.request_id)
        print(e.error_code)
        print(e.error_msg)

# 获取所有子网id 列表
def list_all_subnets()-> List[Dict[str, str]]:
        """获取所有子网信息列表"""
        try:
            client=get_vpc_client()
            request = ListSubnetsRequest()
            response = client.list_subnets(request)
            subnets = []
            if response.subnets:
                for subnet in response.subnets:
                    subnets.append({
                        'id': subnet.id,
                        'name': subnet.name,
                        'cidr': subnet.cidr,
                        'vpc_id': subnet.vpc_id,
                        'status': subnet.status
                    })
            return subnets
            
        except exceptions.ClientRequestException as e:
            logger.error(f"获取子网列表失败: {e.error_msg}")
            raise
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            raise

# 获取子网id
def get_subnet_id(subnet_name: Optional[str] = None, 
                     vpc_id: Optional[str] = None) -> Optional[str]:
        """
        获取子网ID
        :param subnet_name: 子网名称(可选)
        :param vpc_id: VPC ID(可选)
        :return: 子网ID或None
        """
        try:
            subnets = list_all_subnets()
            
            # 如果没有过滤条件，返回第一个子网ID
            if not subnet_name and not vpc_id:
                if subnets:
                    logger.info(f"返回第一个子网ID: {subnets[0]['id']}")
                    return subnets[0]['id']
                return None
            
            # 根据条件过滤子网
            for subnet in subnets:
                match = True
                if subnet_name and subnet['name'] != subnet_name:
                    match = False
                if vpc_id and subnet['vpc_id'] != vpc_id:
                    match = False
                if match:
                    logger.info(f"找到匹配子网: {subnet}")
                    return subnet['id']
            
            logger.warning("未找到匹配的子网")
            return None
            
        except Exception as e:
            logger.error(f"获取子网ID出错: {str(e)}")
            raise

if __name__ == "__main__":
   
    get_vpc_id()
    get_subnet_id()
   