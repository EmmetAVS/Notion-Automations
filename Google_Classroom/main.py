from google_auth_oauthlib.flow import InstalledAppFlow
import requests as r
import json
from datetime import datetime as dt, timezone
from Utils.notion import confirm_notion_database, list_db_items
from Canvas.main import database_format, expected_title
import copy

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
]

def parse_due(due_date, due_time):
    year = due_date.get("year")
    month = due_date.get("month")
    day = due_date.get("day")
    hours = due_time.get("hours", 0)
    minutes = due_time.get("minutes", 0)
    dt_obj = dt(year, month, day, hours, minutes, tzinfo=timezone.utc)
    return dt_obj.isoformat()

def get_courses(token):
    
    next_page_token = None
    first_page = True
    courses = []
    
    while first_page or next_page_token:
        
        params = {
            "studentId": "me",
            "courseStates": "ACTIVE",
        }
        
        if next_page_token:
            params["pageToken"] = next_page_token
        
        response = r.get(
            "https://classroom.googleapis.com/v1/courses",
            headers = {
                "Authorization": f"Bearer {token}",
            },
            params = params
        )
    
        first_page = False
        response.raise_for_status()
        response_json = response.json()
        next_page_token = response_json.get("nextPageToken")
        courses.extend(response_json.get("courses", []))
        
    return [
        {
            "id": course['id'],
            "name": course['name'],
            "link": course['alternateLink']
        } for course in courses
    ]

def get_course_work(token, course_id, course_name):
    
    next_page_token = None
    first_page = True
    
    course_work = []

    while first_page or next_page_token:
        response = r.get(
            f"https://classroom.googleapis.com/v1/courses/{course_id}/courseWork",
            headers = {
                "Authorization": f"Bearer {token}",
            }, params = {
                "courseWorkStates": "PUBLISHED",
            }
        )
    
        response.raise_for_status()
        
        first_page = False
        response_json = response.json()
        course_work.extend(response_json.get("courseWork", []))
        next_page_token = response_json.get("nextPageToken")

    course_work = [
        {
            "courseId": course_id,
            "courseName": course_name,
            "id": item['id'],
            "title": item['title'],
            "due_at": parse_due(item.get('dueDate', {}), item.get('dueTime', {})),
            "link": item['alternateLink']
        } for item in course_work
    ]
    
    for course in course_work:
        
        first_page = True
        next_page_token = None

        submission_list = []

        while first_page or next_page_token:
            response = r.get(
                f"https://classroom.googleapis.com/v1/courses/{course['courseId']}/courseWork/{course['id']}/studentSubmissions",
                headers = {
                    "Authorization": f"Bearer {token}",
                    "userId": "me",
                }
            )
            
            response.raise_for_status()
            response_json = response.json()
            submission_list.extend(response_json.get("studentSubmissions", []))
            next_page_token = response_json.get("nextPageToken")
            first_page = False

        submission_list.sort(key=lambda x: dt.fromisoformat(x['updateTime'].replace("Z", "+00:00")))
        
        status = "Not started"
        if submission_list:
            last_submission = submission_list[-1]
            if last_submission['state'] == 'RETURNED':
                status = "Graded"
            elif last_submission['state'] == 'TURNED_IN':
                status = "Submitted"
            else:
                status = "In progress"
                
        course['status'] = status

        #print(json.dumps(submission_list, indent=2))

    return course_work

def confirm_notion_database_wrapper(data, courses):
    
    special_properties = {
        "Course": [{"name": course['name']} for course in courses],
        "Status": [
            {"name": "Not started", "color": "red"},
            {"name": "In progress", "color": "yellow"},
            {"name": "Submitted", "color": "blue"},
            {"name": "Graded", "color": "green"}
        ]
    }
    
    copied_database_format = copy.deepcopy(database_format)
    copied_database_format['properties']['Google_Classroom_Assignment_Id'] = {
            "rich_text": {}
    }

    id, properties = confirm_notion_database(data, expected_title, copied_database_format, special_properties)

    return id, properties

def upload_notion_pages(data, assignments, id):

    items = list_db_items(id, data['Notion']['Notion-API-Key'])
    
    existing_items = [
        item['properties']["Google_Classroom_Assignment_Id"]["rich_text"][0]["text"]["content"] for item in items
        if item['properties']["Google_Classroom_Assignment_Id"]["rich_text"]
    ]
    
    for assignment in assignments:
        
        if assignment['id'] in existing_items:
            continue

        if dt.fromisoformat(assignment['due_at'].replace("Z", "+00:00")) < dt.now(timezone.utc) and assignment['status'] != "Not started":
            continue

        properties = {}
        properties.update({
            "Due Date": {
                "date": {
                    "start": assignment['due_at'],
                    "end": None,
                    "time_zone": None
                }
            },
            "Status": {
                "select": {
                    "name": assignment['status']
                }
            },
            "Course": {
                "select": {
                    "name": assignment['courseName']
                }
            },
            "Google_Classroom_Assignment_Id": {
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
                            "content": assignment['title']
                        }
                    }
                ]
            },
            "Link": {
                "url": assignment['link']
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

    assignment_map = {
        assignment['id']: assignment for assignment in assignments
    }
    
    for item in items:
        
        if not item['properties']["Google_Classroom_Assignment_Id"]["rich_text"]:
            continue
        
        assignment = assignment_map.get(item['properties']["Google_Classroom_Assignment_Id"]["rich_text"][0]["text"]["content"])
        if not assignment:
            continue
        
        

        new_status = item['properties']['Status']['select']['name']
        if assignment['status'] in ["Graded", "Submitted"]:
            new_status = assignment['status']
        
        r.patch(f"https://api.notion.com/v1/pages/{item['id']}",
            headers = {
                'Authorization': f"Bearer {data['Notion']['Notion-API-Key']}",
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28'
            },
            json= {
            "properties": {
                "Due Date": {
                    "date": {
                        "start": assignment['due_at'],
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
                    "url": assignment['link']
                }
            }
        })

def main(stop_event, config):
    with config.lock:
        data = copy.deepcopy(config.get_data())
    flow = InstalledAppFlow.from_client_secrets_file(data['Google_Classroom']['client_secret_file'], SCOPES)
    creds = flow.run_local_server(port=0)
    token = creds.token
    courses = get_courses(token)
    
    course_work = []

    for course in courses:
        #print(f"Course: {course['name']}")
        course_assignments = get_course_work(token, course['id'], course['name'])
        #print(f"Course Work: {json.dumps(course_assignments, indent=2)}")
        course_work.extend(course_assignments)

    id, properties = confirm_notion_database_wrapper(data, courses)
    
    #print(json.dumps(course_work, indent=2))
    upload_notion_pages(data, course_work, id)