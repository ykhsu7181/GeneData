import requests


def fetch_rgi_ogigraph(ogi_id):
    url = f"https://riceome.hzau.edu.cn/dev/home_img/ogigraph/json/{ogi_id}.json"

    session = requests.Session()
    session.trust_env = False

    response = session.get(url, timeout=30, verify=True)
    response.raise_for_status()
    return response.json()