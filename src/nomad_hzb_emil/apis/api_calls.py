import requests
import getpass

proxies = {
    "http": "http://proxy.csn29.bessy.de:3128",
    "https": "http://proxy.csn29.bessy.de:3128",
}

def init_cache():
    import requests_cache
    requests_cache.install_cache("my_local_cache", allowable_methods=('GET', 'POST'), ignored_parameters=['Authorization'])
    
def get_all_uploads(url, token, number_of_uploads=20):
    response = requests.get(f'{url}/uploads',
                             headers={'Authorization': f'Bearer {token}'},params=dict(page_size=number_of_uploads,order_by='upload_create_time', order="desc"))
    return response.json()["data"]

def get_template(url, token, upload_name, method):
    query = {
        'required': {
            'data': '*',
        },
        'owner': 'visible',
        'query': {"upload_name": upload_name, "entry_type":method},
        'pagination': {
            'page_size': 100
        }
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    return response.json()["data"]
    
def get_token(url, name=None):
    user = name if name is not None else input("Username")
    print("Passwort: \n")
    password = getpass.getpass()
    
    # Get a token from the api, login
    response = requests.get(
        f'{url}/auth/token', params=dict(username=user, password=password))    
    return response.json()['access_token']

def get_entry_data(url, token, entry_id):

    row = {"entry_id": entry_id}
    query = {
        'required': {
            'metadata': '*',
            'data': '*',
        },
        'owner': 'visible',
        'query': row,
        'pagination': {
            'page_size': 100
        }
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    assert len(response.json()["data"]) ==1, "Entry not found"
    return response.json()["data"][0]["archive"]["data"]

def get_entry_meta_data(url, token, entry_id):

    row = {"entry_id": entry_id}
    query = {
        'required': {
            'metadata': '*',
        },
        'owner': 'visible',
        'query': row,
        'pagination': {
            'page_size': 100
        }
    }
    response = requests.post(f'{url}/entries/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    assert len(response.json()["data"]) ==1, "Entry not found"
    return response.json()["data"][0]

def get_information(url, token, entry_id, path):
    mdata = get_entry_meta_data(url, token, entry_id)
    res = []
    for ref in mdata.get("entry_references"):
        if path != ref.get("source_path"):
            continue
        res.append(get_entry_data(url, token, ref.get("target_entry_id")))
        
    return res


def get_setup(url, token, entry_id):
    data = get_information(url, token, entry_id, "data.setup")
    assert data and len(data) == 1, "No Setup found"
    return data[0]

def get_environment(url, token, entry_id):
    data = get_information(url, token, entry_id, "data.environment")
    assert data and len(data) == 1, "No Environment found"
    return data[0]
    
def get_samples(url, token, entry_id):
    data = get_information(url, token, entry_id, "data.samples.reference")
    assert data and len(data) > 0, "No Samples found"
    return data


def get_entryid(url, token, sample_id):  # give it a batch id
    # get al entries related to this batch id
    query = {
        'required': {
            'metadata': '*'
        },
        'owner': 'visible',
        'query': {'results.eln.lab_ids': sample_id},
        'pagination': {
            'page_size': 100
        }
    }
    response = requests.post(
        f'{url}/entries/query', headers={'Authorization': f'Bearer {token}'}, json=query)
    data = response.json()["data"]
    if len(data) != 1:
        return None
    return data[0]["entry_id"]

def get_nomad_ids_of_entry(url, token, sample_id):  # give it a batch id
    # get al entries related to this batch id
    query = {
        'required': {
            'metadata': '*'
        },
        'owner': 'visible',
        'query': {'results.eln.lab_ids': sample_id},
        'pagination': {
            'page_size': 1000
        }
    }
    response = requests.post(
        f'{url}/entries/query', headers={'Authorization': f'Bearer {token}'}, json=query)
    data = response.json()["data"]
    assert len(data) == 1
    return data[0]["entry_id"], data[0]["upload_id"]

def get_specific_data_of_sample(url, token, sample_id, entry_type, with_meta=False):
    # collect the results of the sample, in this case it are all the annealing temperatures
    entry_id = get_entryid(url, token, sample_id)
    
    query = {
        'required': {
            'metadata': '*',
            'data': '*',
        },
        'owner': 'visible',
        'query': {'entry_references.target_entry_id': entry_id},
        'pagination': {
            'page_size': 1000
        }
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    linked_data = response.json()["data"]
    res = []
    for ldata in linked_data:
        if entry_type not in ldata["archive"]["metadata"].get("entry_type", ""):
            continue
        if with_meta:
            res.append((ldata["archive"]["data"],ldata["archive"]["metadata"]))
        else:
            res.append(ldata["archive"]["data"])
    return res 

def set_value_in_archive(url, token, md, key, value):
    import json
    row = {"entry_id": md["entry_id"]}
    query = {
        'required': {
            'data': '*',
        },
        'owner': 'visible',
        'query': row,
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    assert len(response.json()["data"]) ==1, "Entry not found"
    data = response.json()["data"][0]["archive"]["data"]
    data[key] = value 
    response = requests.put(f'{url}/uploads/{md["upload_id"]}/raw/',
                            headers={'Authorization': f'Bearer {token}'}, data={"wait_for_processing":True},
                            files={'file':(md["mainfile"], json.dumps({"data":data}), "application/json")})
    
def get_specific_data_of_uploads(url, token, upload_list, entry_type, with_meta=False):   
    query = {
        'required': {
            'metadata': '*',
            'data': '*',
        },
        'owner': 'visible',
        'query': {'upload_name:any': upload_list},
        'pagination': {
            'page_size': 1000
        }
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    linked_data = response.json()["data"]
    res = []
    for ldata in linked_data:
        if entry_type not in ldata["archive"]["metadata"].get("entry_type", ""):
            continue
        if with_meta:
            res.append((ldata["archive"]["data"],ldata["archive"]["metadata"]))
        else:
            res.append(ldata["archive"]["data"])
    return res 

def get_specific_entrytype_of_uploads(url, token, upload_list, entry_type, with_meta=False):   
    # in comparison to the query above this method requires the exact nomad entry_type (e.g. CE_NOME_Chronoamperometry instead of Chronoamperometry)
    query = {
        'required': {
            'metadata': '*',
            'data': '*',
        },
        'owner': 'visible',
        'query': {
            'upload_name:any': upload_list,
            'entry_type': entry_type
        },
        'pagination': {
            'page_size': 10000
        }
    }
    response = requests.post(f'{url}/entries/archive/query',
                             headers={'Authorization': f'Bearer {token}'}, json=query)
    linked_data = response.json()["data"]
    res = []
    for ldata in linked_data:
        if with_meta:
            res.append((ldata["archive"]["data"],ldata["archive"]["metadata"]))
        else:
            res.append(ldata["archive"]["data"])
    return res 
