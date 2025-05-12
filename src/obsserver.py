import os
import traceback
from mcp.server.fastmcp import FastMCP
from obs import CreateBucketHeader, HeadPermission
from obs import ObsClient

# Initialize OBS server
mcp = FastMCP("obsserver", port=os.getenv("MCPServerPort", 8000))

DEFAULT_SERVER = "https://obs.cn-north-4.myhuaweicloud.com"


def get_endpoint(region_name: str = "北京四") -> str:
    endpoint_list = {
        "约翰内斯堡": "obs.af-south-1.myhuaweicloud.com",
        "香港": "obs.ap-southeast-1.myhuaweicloud.com",
        "曼谷": "obs.ap-southeast-2.myhuaweicloud.com",
        "新加坡": "obs.ap-southeast-3.myhuaweicloud.com",
        "雅加达": "obs.ap-southeast-4.myhuaweicloud.com",
        "上海二": "obs.cn-east-2.myhuaweicloud.com",
        "上海一": "obs.cn-east-3.myhuaweicloud.com",
        "北京一": "obs.cn-north-1.myhuaweicloud.com",
        "北京四": "obs.cn-north-4.myhuaweicloud.com",
        "乌兰察布一": "obs.cn-north-9.myhuaweicloud.com",
        "广州": "obs.cn-south-1.myhuaweicloud.com",
        "深圳": "obs.cn-south-2.myhuaweicloud.com",
        "广州-友好用户环境": "obs.cn-south-4.myhuaweicloud.com",
        "贵阳一": "obs.cn-southwest-2.myhuaweicloud.com",
        "墨西哥城二": "obs.la-north-2.myhuaweicloud.com",
        "圣地亚哥": "obs.la-south-2.myhuaweicloud.com",
        "墨西哥城一": "obs.na-mexico-1.myhuaweicloud.com",
        "圣保罗一": "obs.sa-brazil-1.myhuaweicloud.com",
        "伊斯坦布尔": "obs.tr-west-1.myhuaweicloud.com"}

    if region_name in endpoint_list:
        return "https://" + endpoint_list[region_name]

    return DEFAULT_SERVER


def get_obs_endpoint(region: str = "") -> str:
    endpoint_list = {
        "af-south-1": "obs.af-south-1.myhuaweicloud.com",
        "ap-southeast-1": "obs.ap-southeast-1.myhuaweicloud.com",
        "ap-southeast-2": "obs.ap-southeast-2.myhuaweicloud.com",
        "ap-southeast-3": "obs.ap-southeast-3.myhuaweicloud.com",
        "ap-southeast-4": "obs.ap-southeast-4.myhuaweicloud.com",
        "cn-east-2": "obs.cn-east-2.myhuaweicloud.com",
        "cn-east-3": "obs.cn-east-3.myhuaweicloud.com",
        "cn-north-1": "obs.cn-north-1.myhuaweicloud.com",
        "cn-north-4": "obs.cn-north-4.myhuaweicloud.com",
        "cn-north-9": "obs.cn-north-9.myhuaweicloud.com",
        "cn-south-1": "obs.cn-south-1.myhuaweicloud.com",
        "cn-south-2": "obs.cn-south-2.myhuaweicloud.com",
        "cn-south-4": "obs.cn-south-4.myhuaweicloud.com",
        "cn-southwest-2": "obs.cn-southwest-2.myhuaweicloud.com",
        "la-north-2": "obs.la-north-2.myhuaweicloud.com",
        "la-south-2": "obs.la-south-2.myhuaweicloud.com",
        "na-mexico-1": "obs.na-mexico-1.myhuaweicloud.com",
        "sa-brazil-1": "obs.sa-brazil-1.myhuaweicloud.com",
        "tr-west-1": "obs.tr-west-1.myhuaweicloud.com"}

    if region in endpoint_list:
        return "https://" + endpoint_list[region]

    return DEFAULT_SERVER


def get_obsclient(server: str) -> ObsClient:
    ak = os.getenv("AccessKeyID")
    sk = os.getenv("SecretAccessKey")
    return ObsClient(access_key_id=ak, secret_access_key=sk, server=server)


def get_bucket_region_url(bucket_name: str, region: str = "北京四") -> str:
    """获取用户桶所在区域的URL.

    Args:
        bucket_name: 桶名称
        region: 地域 (e.g. 北京四, 上海二, 香港)
    """

    obsClient = get_obsclient(DEFAULT_SERVER)
    try:
        # 列举桶，并设置isQueryLocation参数为True，同时查询桶区域
        resp = obsClient.listBuckets(True)
        if resp.status < 300:
            for bucket in resp.body.buckets:
                if bucket_name == bucket.name:
                    return get_obs_endpoint(bucket.location)
            return DEFAULT_SERVER
        else:
            return DEFAULT_SERVER
    except Exception:
        return DEFAULT_SERVER


@mcp.tool()
def get_buckets(region: str = "北京四") -> str:
    """根据地域信息获取用户桶列表.

    Args:
        region: 地域 (e.g. 北京四, 上海二, 香港)
    """
    server = get_endpoint(region)
    obsClient = get_obsclient(server)
    try:
        # 列举桶，并设置isQueryLocation参数为True，同时查询桶区域
        resp = obsClient.listBuckets(True)
        # 返回码为2xx时，接口调用成功，否则接口调用失败
        buckets_info = []
        if resp.status < 300:
            for bucket in resp.body.buckets:
                bucket_info = f"""
                    {'name:', bucket.name,
                     'location:', bucket.location,
                     'type', bucket.bucket_type}
                """
                buckets_info.append(bucket_info)
            return "\n\n".join(buckets_info)
        else:
            return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息: " + traceback.format_exc()


@mcp.tool()
def get_objects(bucket_name: str, region: str = "北京四") -> str:
    """根据桶名称、地域获取用户桶中对象列表.

    Args:
        bucket_name: 桶名称
        region: 地域 (e.g. 北京四, 上海二, 香港)
    """

    server = get_bucket_region_url(bucket_name, region)
    obsClient = get_obsclient(server)
    try:
        # 指定单次列举对象个数为100
        max_keys = 100

        # 列举桶内对象
        resp = obsClient.listObjects(bucket_name, max_keys=max_keys, encoding_type='url')

        # 返回码为2xx时，接口调用成功，否则接口调用失败
        if resp.status < 300:
            contents_info = []
            for content in resp.body.contents:
                if not content.key.endswith("/"):
                    content_info = f"""
                        {'key:', content.key,
                         'size:', content.size,
                         'lastModified:', content.lastModified,
                         'storageClass:', content.storageClass}
                    """
                    contents_info.append(content_info)
            return "\n\n".join(contents_info)
        else:
            return get_resp_msg(resp)
    except Exception:
        return "操作失败,错误信息：" + traceback.format_exc()


@mcp.tool()
def bucket_exist(bucket_name: str, region_name: str) -> str:
    """根据桶名称、地域判断桶是否存在.

    Args:
        bucket_name: 桶名称
        region_name: 地域 (e.g. 北京四, 上海二, 香港)
    """
    server = get_endpoint(region_name)
    obsClient = get_obsclient(server)
    try:
        # 判断桶是否存在
        resp = obsClient.headBucket(bucket_name)
        # 返回码为2xx时，接口调用成功，否则接口调用失败
        if resp.status < 300:
            return "存在"
        elif resp.status == 404:
            return "不存在"
        else:
            return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息：" + str(traceback.format_exc())


@mcp.tool()
def delete_bucket(bucket_name: str, region_name: str) -> str:
    """根据桶名称、地域信息删除桶.

    Args:
        bucket_name: 桶名称
        region_name: 地域 (e.g. 北京四, 上海二, 香港)
    """

    server = get_endpoint(region_name)
    obsClient = get_obsclient(server)
    try:
        resp = obsClient.deleteBucket(bucket_name)
        return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息：" + traceback.format_exc()


def get_location_from_server(server: str) -> str:
    return server.split('.')[1]


STORAGE_MAPPING = {
    "归档存储": "COLD",
    "低频访问存储": "WARM"
}


def get_storage_class(storage: str) -> str:
    return STORAGE_MAPPING.get(storage, "STANDARD")


def get_azs(az: str) -> str:
    return "3az" if not az.strip() else None


@mcp.tool()
def create_bucket(bucket_name: str, region_name: str, storage_class: str,
                  available_zone: str) -> str:
    """根据桶名称、地域、存储类别、AZ类型创建用户桶.

    Args:
        bucket_name: 桶名称
        region_name: 地域 (e.g. 北京四, 上海二, 香港)
        storage_class: 存储类别包括, 标准存储:STANDARD;低频访问存储:WARM;归档存储:COLD
        available_zone: AZ类型包括: 多AZ:3az;单AZ:默认值
    """

    server = get_endpoint(region_name)
    location = get_location_from_server(server)
    obsClient = get_obsclient(server)
    try:
        # 创建桶的附加头域，桶的访问控制策略是私有桶
        sc = get_storage_class(storage_class)
        az = get_azs(available_zone)
        if az:
            header = CreateBucketHeader(aclControl=HeadPermission.PRIVATE, storageClass=sc, availableZone=az)
        else:
            header = CreateBucketHeader(aclControl=HeadPermission.PRIVATE, storageClass=sc)

        # 创建桶
        resp = obsClient.createBucket(bucket_name, header, location)
        return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息：" + traceback.format_exc()


def get_resp_msg(resp) -> str:
    if resp.status < 300:
        return "操作成功"

    error_msg = getattr(resp, 'errorMessage', None)
    status_code = getattr(resp, 'status', '未知')

    return f"操作失败，{f'错误信息：{error_msg}' if error_msg else f'错误码：{status_code}'}"


@mcp.tool()
def download_object(bucket_name: str, region_name: str,
                    object_key: str, local_file: str) -> str:
    """根据桶名称、地域、对象名称下载对象的内容保存到本地文件中.

    Args:
        bucket_name: 桶名称
        region_name: 地域 (e.g. 北京四, 上海二, 香港)
        object_key: 对象名称
        local_file: 本地文件，需要包含路径
    """

    server = get_endpoint(region_name)
    obsClient = get_obsclient(server)
    try:
        resp = obsClient.getObject(bucket_name, object_key, local_file)
        return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息：" + traceback.format_exc()


@mcp.tool()
def delete_object(bucket_name: str, region_name: str,
                  object_key: str) -> str:
    """根据桶名称、地域、对象名称删除桶中对象.

    Args:
        bucket_name: 桶名称
        region_name: 地域 (e.g. 北京四, 上海二, 香港)
        object_key: 对象名称
    """

    server = get_endpoint(region_name)
    obsClient = get_obsclient(server)
    try:
        resp = obsClient.deleteObject(bucket_name, object_key)
        return get_resp_msg(resp)
    except Exception:
        return "操作失败，错误信息：" + traceback.format_exc()


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport=os.getenv("ServerTransport", "stdio"))
