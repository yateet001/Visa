import requests, sys, json
def get_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'client_id': client_id,
        'scope': 'https://analysis.windows.net/powerbi/api/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    r = requests.post(url, data=data)
    if r.status_code != 200:
        print('TOKEN_ERROR', r.status_code, r.text)
        raise SystemExit('Failed to acquire token')
    return r.json()['access_token']

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--tenant')
    p.add_argument('--client')
    p.add_argument('--secret')
    args=p.parse_args()
    print(get_token(args.tenant, args.client, args.secret))
