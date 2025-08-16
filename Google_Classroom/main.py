from google_auth_oauthlib.flow import InstalledAppFlow
import requests as r
import json
from datetime import datetime as dt, timezone

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

def get_course_work(token, course_id):
    
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

    return [
        {
            "courseId": course['id'],
            "id": course['id'],
            "title": course['title'],
            "due_at": parse_due(course.get('dueDate', {}), course.get('dueTime', {})),
            "link": course['alternateLink']
        } for course in course_work
    ]

def main(stop_event, config):
    with config.lock:
        flow = InstalledAppFlow.from_client_secrets_file(config.get_data()['Google_Classroom']['client_secret_file'], SCOPES)
    creds = flow.run_local_server(port=0)
    token = creds.token
    courses = get_courses(token)

    for course in courses:
        print(f"Course: {course['name']}")
        print(f"Course Work: {json.dumps(get_course_work(token, course['id']), indent=2)}")