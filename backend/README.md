
# Python Backend

## Core Components

- `core/models.py` - Start with the domain models since they're the foundation of everything else. Getting these right is critical as all other components depend on them.
- `tests/test_models.py` - Write tests for these models right away to ensure they work as expected. This follows good TDD principles.
- `core/overlap_engine.py` - Implement the core algorithm that will find overlapping time slots, which is central to the application's functionality.
- `tests/test_overlap_engine.py` - Test the overlap algorithm thoroughly, especially with different timezone scenarios.
- `adapters/calendly.py` - Implement the first adapter since many calendar services use Calendly.
- `adapters/google_calendar.py` - Implement the second adapter for Google Calendar integration.
- `tests/test_adapters.py` - Write tests for both adapters to ensure they correctly extract availability information.
- `adapters/output/link_generator.py` - Implement the output generator to create shareable links.
- `api/main.py` - Implement the API layer that ties everything together with FastAPI.
- `tests/test_api.py` - Write integration tests for the API endpoints.