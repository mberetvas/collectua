import asyncio
from asyncua import Client

async def main():
    client = Client(url='opc.tcp://localhost:50000', timeout=5)
    eps = await client.connect_and_get_server_endpoints()
    print(f'endpoint_count={len(eps)}')
    for i, ep in enumerate(eps, 1):
        app = getattr(getattr(ep, 'Server', None), 'ApplicationUri', None)
        sec = getattr(ep, 'SecurityPolicyUri', None)
        mode = getattr(getattr(ep, 'SecurityMode', None), 'name', None)
        url = getattr(ep, 'EndpointUrl', None)
        print(f'[{i}] url={url}')
        print(f'    app_uri={app}')
        print(f'    sec={sec}')
        print(f'    mode={mode}')

asyncio.run(main())
