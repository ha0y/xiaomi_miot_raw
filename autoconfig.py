import requests

url_all = 'http://miot-spec.org/miot-spec-v2/instances?status=all'
url_spec = 'http://miot-spec.org/miot-spec-v2/instance'


def deviceinfo(j):
    print(f"设备描述：{j['description']}")
    print("设备属性：")
    for s in j['services']:
        print(f"\nsiid {s['iid']}: {s['description']}\n")
        for p in s.get('properties', []):
            print(f"   piid {p['iid']}: {p['description']}", end=' ')
            if 'read' in p['access']:
                print("可读取", end=' ')
            if 'write' in p['access']:
                print("可控制", end=' ')
            print()
            if 'format' in p:
                print(f"      数据类型：{p['format']}")

            if 'value-range' in p:
                print(f"      取值范围：{p['value-range']}")
            if 'value-list' in p:
                print(f"      取值范围：")
                for item in p['value-list']:
                    print(f"         {item['value']}: {item['description']}")
        for a in s.get('actions', []):
            print(f"   aiid {a['iid']}: {a['description']}", end=' ')
            print()
        print()

if __name__ == '__main__':
    print("正在加载设备列表...")
    dev_list = requests.get(url_all).json().get('instances')
    print(f"加载成功，现已支持{len(dev_list)}个设备")

    model_ = input("请输入设备model:")

    result = []
    for item in dev_list:
        if model_ in item['model'] or model_ in item['type']:
            result.append(item)

    # print(result)
    if result:
        print("已发现以下设备")
        print("--------------------------------------")
        print("序号\t        model \t          urn")
        for idx, item in enumerate(result):
            print(f"{idx+1}\t{item['model']}\t{item['type']}")
        if len(result) > 1:
            inp = input("请确认哪个是你的设备，输入序号：")
            urn = result[int(inp)-1]['type']
        else:
            urn = result[0]['type']

        params = {'type': urn}
        r = requests.get(url_spec, params=params).json()
        # print(r)

        deviceinfo(r)

    else:
        print("未找到相关设备")

input("按任意键退出...")