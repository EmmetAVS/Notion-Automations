from email import header
from wsgiref import headers
import requests as r
import copy
import json
from datetime import datetime as dt, timezone
from bs4 import BeautifulSoup as bs
from Utils.notion import confirm_notion_database, list_db_items

integration_title = "Canvas"

config_defaults = {
    "canvases": [
        
    ]
}

canvas_defaults = {
    "canvas-api-url": None,
    "canvas-api-token": None,
    "excluded-course-codes": [],
}

expected_title = "School Tasks"

database_format = {
    "properties": {
        "Name": {
            "title": {}
        },
        "Due Date": {
            "date": {}
        },
        "Description": {
            "rich_text": {}
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Not started", "color": "red"},
                    {"name": "In progress", "color": "yellow"},
                    {"name": "Submitted", "color": "blue"},
                    {"name": "Graded", "color": "green"}
                ]
            }
        },
        "Course": {
            "select": {
                "options": [
                ]
            }
        },
        "Canvas-Assignment-ID": {
            "rich_text": {}
        },
        "Link": {
            "url": {}
        }
    }
}

def get_assignments(course, user_id, api_key):
    
    response = r.get(f"{course['url']}/assignments", headers={
        "Authorization": f"Bearer {api_key}",
    })
    
    response.raise_for_status()
    
    assignments = []

    for assignment in response.json():
        if not assignment.get('due_at'):
            continue

        submissions_response = r.get(f"{course['url']}/assignments/{assignment['id']}/submissions/{user_id}", headers={
                "Authorization": f"Bearer {api_key}",
            })

        submissions_response.raise_for_status()
        submissions = submissions_response.json()
        

        assignments.append({
            "id": str(assignment['id']),
            "name": assignment['name'],
            "due_at": assignment['due_at'],
            "description": assignment['description'],
            "submitted": False,
            "graded": False,
            "course": course['name'],
            "url": assignment.get('html_url', "")
        })

        assignments[-1]['submitted'] = submissions.get('workflow_state') in ['submitted', 'graded']
        assignments[-1]['graded'] = submissions.get('workflow_state') == 'graded'

    return assignments

def confirm_notion_database_wrapper(data, assignments):
    
    now = dt.now(timezone.utc)
    
    new_assignments = [
        assignment for assignment in assignments if dt.fromisoformat(assignment['due_at'].replace("Z", "+00:00")) >= now
    ]

    other_assignments = [
        assignment for assignment in assignments if dt.fromisoformat(assignment['due_at'].replace("Z", "+00:00")) < now
    ]

    courses = [
        {"name": name}
        for name in {assignment['course'] for assignment in new_assignments}
    ]
    

    special_properties = {
        "Course": courses,
        "Status": [
            {"name": "Not started", "color": "red"},
            {"name": "In progress", "color": "yellow"},
            {"name": "Submitted", "color": "blue"},
            {"name": "Graded", "color": "green"}
        ]
    }
    
    id, properties = confirm_notion_database(data, expected_title, database_format, special_properties)

    return (id, properties, new_assignments, other_assignments)
        
def update_notion(assignments, data):
    
    id, base_properties, new_assignments, other_assignments = confirm_notion_database_wrapper(data, assignments)
    items = list_db_items(id, data['Notion']['Notion-API-Key'])

    existing_items = [
        item['properties']["Canvas-Assignment-ID"]["rich_text"][0]["text"]["content"] for item in items
        if item['properties']["Canvas-Assignment-ID"]["rich_text"]
    ]
    
    for assignment in new_assignments:

        if assignment['id'] in existing_items:
            continue
        
        time = dt.fromisoformat(assignment['due_at'].replace("Z", "+00:00"))

        soup = bs(assignment.get("description", ""), "html.parser")
        try:
            text = soup.get_text(separator="\n").strip()
        except TypeError:
            text = assignment.get("description", "")
        text = f"{text[0:1997]}..." if len(text) > 2000 else text

        properties = {}
        properties.update({
            "Description": {
                "rich_text": [
                    {
                        "text": {
                            "content": text
                        }
                    }
                ]
            },
            "Due Date": {
                "date": {
                    "start": time.isoformat(timespec='milliseconds'),
                    "end": None,
                    "time_zone": None
                }
            },
            "Status": {
                "select": {
                    "name": "Graded" if assignment['graded'] else "Submitted" if assignment['submitted'] else "Not started"
                }
            },
            "Course": {
                "select": {
                    "name": assignment['course']
                }
            },
            "Canvas-Assignment-ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": assignment['id']
                        }
                    }
                ]
            },
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": assignment['name']
                        }
                    }
                ]
            },
            "Link": {
                "url": assignment['url']
            }
        })
        
        response = r.post(
            "https://api.notion.com/v1/pages",
            headers = {
                'Authorization': f"Bearer {data['Notion']['Notion-API-Key']}",
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28'
            },
            json = {
                "parent": {
                    "database_id": id
                },
                "properties": properties
            }
        )
        
        if response.status_code != 200:
            print(response.text)
            print(json.dumps(properties, indent=4))
        response.raise_for_status()

    new_assignments.extend(other_assignments)
    assignment_map = {
        assignment['id']: assignment for assignment in new_assignments
    }

    for assignment in items:
        if not assignment['properties']["Canvas-Assignment-ID"]["rich_text"]:
            continue
        assignment_details = assignment_map.get(assignment['properties']["Canvas-Assignment-ID"]["rich_text"][0]["text"]["content"])
        if not assignment_details:
            continue

        time = dt.fromisoformat(assignment_details['due_at'].replace("Z", "+00:00"))
        old_status = assignment['properties']["Status"]["select"]["name"]

        if assignment_details['graded']:
            new_status = "Graded"
        elif assignment_details['submitted']:
            new_status = "Submitted"
        else:
            new_status = old_status

        r.patch(f"https://api.notion.com/v1/pages/{assignment['id']}",
            headers = {
                'Authorization': f"Bearer {data['Notion']['Notion-API-Key']}",
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28'
            },
            json= {
            "properties": {
                "Due Date": {
                    "date": {
                        "start": time.isoformat(timespec='milliseconds'),
                        "end": None,
                        "time_zone": None
                    }
                },
                "Status": {
                    "select": {
                        "name": new_status
                    }
                },
                "Link": {
                    "url": assignment_details['url']
                }
            }
        })

def scrape_assignments(data):
    
    all_assignments = []

    for canvas in data[integration_title]["canvases"]:
        response = r.get("https://canvas.instructure.com/api/v1/courses", headers={
            "Authorization": f"Bearer {canvas['canvas-api-token']}",
        })
        
        response.raise_for_status()
        
        user_response = r.get("https://mvla.instructure.com/api/v1/users/self", headers={
            "Authorization": f"Bearer {canvas['canvas-api-token']}",
        })
        
        user_response.raise_for_status()
        
        user_id = user_response.json()['id']
        
        courses = []
        
        for course in response.json():
            
            try:
                if course['course_code'] in canvas["excluded-course-codes"]:
                    continue
                
                courses.append({
                    "id": course['id'],
                    "name": course['name'],
                    "url": f"{canvas['canvas-api-url']}/api/v1/courses/{course['id']}"
                })
            except KeyError as e:
                pass
        
        
        for course in courses:
            all_assignments.extend(get_assignments(course, user_id, canvas['canvas-api-token']))
            
    return all_assignments

def check_config(config):
    with config.lock:
        data = config.get_data()
        if integration_title not in data:
            data[integration_title] = config_defaults
            config.write_data()
        else:
            for key in config_defaults.keys():
                if key not in data[integration_title]:
                    data[integration_title][key] = config_defaults[key]
                    config.write_data()

        forced_update = False
        for canvas in data[integration_title]["canvases"]:
            for key in canvas_defaults.keys():
                if key not in canvas or canvas[key] is None:
                    forced_update = True
                    canvas[key] = canvas_defaults[key]
                    
        if forced_update:
            config.write_data()
            raise Exception("Canvas Configuration is Incomplete")

def main(stop_event, config):
    try:
        check_config(config)
    except Exception as e:
        print(f"Error in Canvas integration: {e}")
        stop_event.set()
        
    if not stop_event.is_set():
        
        with config.lock:
            data = copy.deepcopy(config.get_data())
        
        assignments = scrape_assignments(data)
        update_notion(assignments, data)