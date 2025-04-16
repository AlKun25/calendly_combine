# Calendly combine

## Initial idea

A simple app in which you paste a bunch of different calendly or google calendar share links, and it generates a new calendly with only the overlapping times, or even autofills a lettucemeet

## Folder structure

```text
calendly_combine/
├── core/
│   ├── __init__.py
│   ├── models.py
│   └── overlap_engine.py
├── adapters/
│   ├── __init__.py
│   ├── calendly.py
│   ├── google_calendar.py
│   └── output/
│       ├── __init__.py
│       └── link_generator.py
├── api/
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_overlap_engine.py
│   ├── test_adapters.py
│   └── test_api.py
├── requirements.txt
└── Dockerfile
```

## Testing Script

Run this from the project root directory

```bash
$$ python -m pytest tests/test_models.py
```
