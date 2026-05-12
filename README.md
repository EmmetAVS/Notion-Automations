# Notion Automations

Steps: 

1. Install dependencies
```
python -m pip install -r requirements.txt
```

2. Setup Config in ```config.json```
   
```
   {
    "Canvas": [
      {
        "canvas-api-url": "https://mvla.instructure.com",
        "canvas-api-token": "...",
        "excluded-course-codes": []
      }
    ],
    "Google_Classroom": {
      "client_secret_file": "client_secret.json"
    },
    "Notion": {
      "Notion-API-Key": "...",
      "parent-page-id": "..."
    }
  }
```  
4. Run with

```
python main.py
```
