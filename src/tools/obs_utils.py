from tools.utils import get_aksk
import logging
from obs import ObsClient


logger = logging.getLogger(__name__)


def get_endpoint(region_name: str) -> str:
    endpoint_list = {
    "约翰内斯堡":"obs.af-south-1.myhuaweicloud.com",
    "香港":"obs.ap-southeast-1.myhuaweicloud.com",
    "曼谷":"obs.ap-southeast-2.myhuaweicloud.com",
    "新加坡":"obs.ap-southeast-3.myhuaweicloud.com",
    "雅加达":"obs.ap-southeast-4.myhuaweicloud.com",
    "上海二":"obs.cn-east-2.myhuaweicloud.com",
    "上海一":"obs.cn-east-3.myhuaweicloud.com",
    "北京一":"obs.cn-north-1.myhuaweicloud.com",
    "北京四":"obs.cn-north-4.myhuaweicloud.com",
    "乌兰察布一":"obs.cn-north-9.myhuaweicloud.com",
    "广州":"obs.cn-south-1.myhuaweicloud.com",
    "深圳":"obs.cn-south-2.myhuaweicloud.com",
    "广州-友好用户环境":"obs.cn-south-4.myhuaweicloud.com",
    "贵阳一":"obs.cn-southwest-2.myhuaweicloud.com",
    "墨西哥城二":"obs.la-north-2.myhuaweicloud.com",
    "圣地亚哥":"obs.la-south-2.myhuaweicloud.com",
    "墨西哥城一":"obs.na-mexico-1.myhuaweicloud.com",
    "圣保罗一":"obs.sa-brazil-1.myhuaweicloud.com",
    "伊斯坦布尔":"obs.tr-west-1.myhuaweicloud.com"}

    if region_name in endpoint_list:
        return "https://" + endpoint_list[region_name]

    raise ValueError("无效地域，请确认地域。")


def get_obsclient(server:str) -> ObsClient:
    ak, sk = get_aksk()
    return ObsClient(access_key_id=ak, secret_access_key=sk, server=server)


def get_location_from_server(server:str) -> str:
    return server.split('.')[1]

