# Notion Automations

Steps: 

1. Install dependencies
```
python -m pip install -r requirements.txt
```

2. Setup Config in ```config.json```
   
```
   {
    "Canvas": {
      "canvases": [
        {
          "canvas-api-url": "https://mvla.instructure.com",
          "canvas-api-token": "...",
          "excluded-course-codes": []
        }
      ]
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
