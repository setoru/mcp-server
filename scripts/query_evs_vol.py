"""Quick EVS volume detail query with correct EVS endpoint."""
import sys, json, yaml
sys.path.insert(0, ".")
from huawei_ecs_delete import CustomClient
from huaweicloudsdkcore.client import ClientBuilder
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.region.region import Region
from huawei_scope import DEFAULT_SCOPE_PATH, EVS_ENDPOINT_TEMPLATE

with open(DEFAULT_SCOPE_PATH) as f:
    scope = yaml.safe_load(f)

ak = scope["ak"]
sk = scope["sk"]
region = scope.get("region", "ap-southeast-3")
project_id = scope.get("project_id")

evs_endpoint = f"https://{EVS_ENDPOINT_TEMPLATE.replace('{region}', region)}"
credentials = BasicCredentials(ak, sk, project_id)
client = (ClientBuilder(CustomClient)
          .with_credentials(credentials)
          .with_region(Region(id=region, endpoint=evs_endpoint))
          .build())

VOL_IDS = [
    ("cce-karpenter-52650-nacsj / 启动盘",  "76803e42-93cc-47e9-b8b5-2d104e64a338"),
    ("cce-karpenter-52650-nacsj / 数据盘",  "b51f2723-778c-4afa-acfc-035f1a995530"),
    ("cce-karpenter-52650-0ften / 启动盘",  "b8e98dc9-1a43-4c22-ab6c-5f19e130b9ed"),
    ("cce-karpenter-52650-0ften / 数据盘",  "4741ea01-c3db-460a-a89a-2882632cc76f"),
]

for label, vid in VOL_IDS:
    try:
        resp = client.do_http_request(
            method="GET",
            resource_path=f"/v2/{project_id}/volumes/{vid}",
            header_params={"Content-Type": "application/json"},
            response_type="json",
        )
        data = resp.json()
        vol = data.get("volume", data)
        print(f"Volume [{label}]: {vid}")
        print(f"  Name:       {vol.get('name','N/A')}")
        print(f"  Size:       {vol.get('size','N/A')} GB")
        print(f"  Status:     {vol.get('status','N/A')}")
        print(f"  Type:       {vol.get('volume_type','N/A')}")
        print(f"  Bootable:   {vol.get('bootable','N/A')}")
        print(f"  Encrypted:  {vol.get('encrypted','N/A')}")
        print(f"  AZ:         {vol.get('availability_zone','N/A')}")
        print()
    except Exception as e:
        print(f"Volume [{label}]: {vid} - Error: {type(e).__name__}: {e}\n")
