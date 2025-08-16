from datetime import datetime as dt, timezone
import requests as r

def confirm_notion_database(data, expected_title, database_format, special_properties):
    headers = {
        "Authorization": f"Bearer {data.get('Notion').get('Notion-API-Key')}",
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28'
    }
    
    parent = {
        "type": "page_id",
        "page_id": data['Notion']["parent-page-id"]
    }
    
    search_request = r.post("https://api.notion.com/v1/search", headers=headers, json={
        "query": expected_title,
        "filter": {
            "value": "database",
            "property": "object"
        },
    })
    
    id = None
    

    search_request.raise_for_status()
    
    for db in search_request.json().get("results", []):
        name = db.get("title", [{}])[0].get("text", {}).get("content", {})
        if name == expected_title:
            id = db.get("id")
            
            for prop in db.get("properties", {}).keys():
                if prop in special_properties.keys():
                    prop_names = [p['name'] for p in special_properties[prop]]
                    for existing_item in db.get("properties", {}).get(prop, {}).get("select", {}).get("options", []):
                        if existing_item['name'] not in prop_names:
                            prop_names.append(existing_item['name'])
                            special_properties[prop].append({"name": existing_item['name']})

            break

    
    for prop in special_properties.keys():
        database_format["properties"][prop]['select']['options'] = special_properties[prop]

    if not id:
        
        database_format["parent"] = parent
        database_format['title'] = [
            {
                "type": "text",
                "text": {
                    "content": expected_title
                }
            }
        ]
        
        created_db_response = r.post(
            "https://api.notion.com/v1/databases",
            headers=headers,
            json=database_format
        )
        created_db_response.raise_for_status()
        id = created_db_response.json().get("id")
        properties = created_db_response.json()['properties']
    else:
        updated_db_response = r.patch(
            f"https://api.notion.com/v1/databases/{id}",
            headers=headers,
            json=database_format
        )
        
        if updated_db_response.status_code != 200:
            print(updated_db_response.text)
        
        updated_db_response.raise_for_status()
        properties = updated_db_response.json()['properties']

    return (id, properties)

def list_db_items(id, token):
    response = r.post(
        "https://api.notion.com/v1/databases/{}/query".format(id),
        headers = {
            "Authorization": f"Bearer {token}",
            'Content-Type': 'application/json',
            'Notion-Version': '2022-06-28'
        }
    )
    
    response.raise_for_status()
    
    return response.json().get("results", [])