"""
Conflict Generator — Creates deterministic, seeded merge conflict scenarios.

Generates synthetic Git merge conflicts for three difficulty levels:
  - Easy: Whitespace / comment conflicts in a single file
  - Medium: Concurrent function modifications with compatible logic
  - Hard: Cross-module refactor collisions spanning multiple files

All episodes are deterministic when given the same seed, ensuring
reproducible grading as required by the OpenEnv spec.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def _count_conflicts(content: str) -> int:
    """Count the number of conflict blocks in file content."""
    return content.count("<<<<<<< ")


# ═══════════════════════════════════════════════════════════════════════════════
# TASK EASY — Whitespace / Comment Conflicts
# ═══════════════════════════════════════════════════════════════════════════════

def generate_easy_episodes() -> List[Dict[str, Any]]:
    """Generate easy-level episodes: whitespace and comment conflicts."""
    episodes = []

    # ── Episode 1: Formatting conflict in a utility function ──
    episodes.append({
        "seed": 42,
        "conflicted_files": {
            "utils.py": (
                'def calculate_total(items, tax_rate=0.1):\n'
                '    """Calculate the total price with tax."""\n'
                '<<<<<<< HEAD\n'
                '    # Calculate subtotal first\n'
                '    subtotal = sum(item["price"] * item["quantity"] for item in items)\n'
                '    \n'
                '    # Apply tax\n'
                '    tax = subtotal * tax_rate\n'
                '    total = subtotal + tax\n'
                '=======\n'
                '    # Sum up all items\n'
                '    subtotal = sum(\n'
                '        item["price"] * item["quantity"]\n'
                '        for item in items\n'
                '    )\n'
                '    # Tax calculation\n'
                '    tax = subtotal * tax_rate\n'
                '    total = subtotal + tax\n'
                '>>>>>>> feature/format-cleanup\n'
                '    return round(total, 2)\n'
                '\n'
                '\n'
                'def format_currency(amount):\n'
                '    """Format a number as currency."""\n'
                '    return f"${amount:,.2f}"\n'
            )
        },
        "git_log_ours": [
            "abc1234 Standardize comment style in utils.py",
            "def5678 Add inline comments for clarity",
        ],
        "git_log_theirs": [
            "111aaaa Reformat calculate_total for readability",
            "222bbbb Apply black formatter to utils.py",
        ],
        "ground_truth": {
            "utils.py": (
                'def calculate_total(items, tax_rate=0.1):\n'
                '    """Calculate the total price with tax."""\n'
                '    # Calculate subtotal first\n'
                '    subtotal = sum(\n'
                '        item["price"] * item["quantity"]\n'
                '        for item in items\n'
                '    )\n'
                '    # Apply tax\n'
                '    tax = subtotal * tax_rate\n'
                '    total = subtotal + tax\n'
                '    return round(total, 2)\n'
                '\n'
                '\n'
                'def format_currency(amount):\n'
                '    """Format a number as currency."""\n'
                '    return f"${amount:,.2f}"\n'
            )
        },
        "test_suite": {
            "test_calculate_total": (
                'def test_calculate_total():\n'
                '    items = [{"price": 10.0, "quantity": 2}, {"price": 5.0, "quantity": 3}]\n'
                '    result = calculate_total(items, tax_rate=0.1)\n'
                '    assert result == 38.5, f"Expected 38.5, got {result}"\n'
                '    return True\n'
            ),
            "test_format_currency": (
                'def test_format_currency():\n'
                '    assert format_currency(1234.5) == "$1,234.50"\n'
                '    return True\n'
            ),
        },
    })

    # ── Episode 2: Docstring and blank line conflict ──
    episodes.append({
        "seed": 123,
        "conflicted_files": {
            "validators.py": (
                '"""Input validation utilities."""\n'
                '\n'
                '\n'
                'def validate_email(email):\n'
                '<<<<<<< HEAD\n'
                '    """Validate an email address format.\n'
                '    \n'
                '    Args:\n'
                '        email: The email string to validate.\n'
                '    \n'
                '    Returns:\n'
                '        bool: True if the email is valid.\n'
                '    """\n'
                '    if not isinstance(email, str):\n'
                '        return False\n'
                '    parts = email.split("@")\n'
                '=======\n'
                '    """Check if email is valid."""\n'
                '    if not isinstance(email, str):\n'
                '        return False\n'
                '\n'
                '    parts = email.split("@")\n'
                '>>>>>>> feature/simplify-docs\n'
                '    if len(parts) != 2:\n'
                '        return False\n'
                '    return "." in parts[1]\n'
                '\n'
                '\n'
                'def validate_age(age):\n'
                '    """Validate age is a positive integer."""\n'
                '    return isinstance(age, int) and 0 < age < 150\n'
            )
        },
        "git_log_ours": [
            "aaa1111 Expand docstrings with Args/Returns",
            "bbb2222 Follow Google docstring convention",
        ],
        "git_log_theirs": [
            "ccc3333 Simplify docstrings for brevity",
            "ddd4444 Add blank lines between logical blocks",
        ],
        "ground_truth": {
            "validators.py": (
                '"""Input validation utilities."""\n'
                '\n'
                '\n'
                'def validate_email(email):\n'
                '    """Validate an email address format.\n'
                '\n'
                '    Args:\n'
                '        email: The email string to validate.\n'
                '\n'
                '    Returns:\n'
                '        bool: True if the email is valid.\n'
                '    """\n'
                '    if not isinstance(email, str):\n'
                '        return False\n'
                '\n'
                '    parts = email.split("@")\n'
                '    if len(parts) != 2:\n'
                '        return False\n'
                '    return "." in parts[1]\n'
                '\n'
                '\n'
                'def validate_age(age):\n'
                '    """Validate age is a positive integer."""\n'
                '    return isinstance(age, int) and 0 < age < 150\n'
            )
        },
        "test_suite": {
            "test_validate_email_valid": (
                'def test_validate_email_valid():\n'
                '    assert validate_email("user@example.com") == True\n'
                '    return True\n'
            ),
            "test_validate_email_invalid": (
                'def test_validate_email_invalid():\n'
                '    assert validate_email("not-an-email") == False\n'
                '    assert validate_email(123) == False\n'
                '    return True\n'
            ),
            "test_validate_age": (
                'def test_validate_age():\n'
                '    assert validate_age(25) == True\n'
                '    assert validate_age(-1) == False\n'
                '    assert validate_age(200) == False\n'
                '    return True\n'
            ),
        },
    })

    # ── Episode 3: Import ordering and blank lines ──
    episodes.append({
        "seed": 256,
        "conflicted_files": {
            "config.py": (
                '"""Application configuration module."""\n'
                '\n'
                '<<<<<<< HEAD\n'
                'import os\n'
                'import sys\n'
                'from pathlib import Path\n'
                '\n'
                '# Default configuration values\n'
                'DEFAULT_PORT = 8080\n'
                'DEFAULT_HOST = "0.0.0.0"\n'
                'DEBUG = os.getenv("DEBUG", "false").lower() == "true"\n'
                '=======\n'
                'import os\n'
                'import sys\n'
                '\n'
                'from pathlib import Path\n'
                '\n'
                '# Configuration defaults\n'
                'DEFAULT_PORT = 8080\n'
                'DEFAULT_HOST = "0.0.0.0"\n'
                'DEBUG = os.getenv("DEBUG", "false").lower() == "true"\n'
                '>>>>>>> feature/isort-cleanup\n'
                '\n'
                '\n'
                'def get_config():\n'
                '    """Return the current configuration as a dict."""\n'
                '    return {\n'
                '        "port": int(os.getenv("PORT", DEFAULT_PORT)),\n'
                '        "host": os.getenv("HOST", DEFAULT_HOST),\n'
                '        "debug": DEBUG,\n'
                '    }\n'
            )
        },
        "git_log_ours": [
            "eee5555 Group imports and add comments",
        ],
        "git_log_theirs": [
            "fff6666 Run isort on config.py",
        ],
        "ground_truth": {
            "config.py": (
                '"""Application configuration module."""\n'
                '\n'
                'import os\n'
                'import sys\n'
                'from pathlib import Path\n'
                '\n'
                '# Default configuration values\n'
                'DEFAULT_PORT = 8080\n'
                'DEFAULT_HOST = "0.0.0.0"\n'
                'DEBUG = os.getenv("DEBUG", "false").lower() == "true"\n'
                '\n'
                '\n'
                'def get_config():\n'
                '    """Return the current configuration as a dict."""\n'
                '    return {\n'
                '        "port": int(os.getenv("PORT", DEFAULT_PORT)),\n'
                '        "host": os.getenv("HOST", DEFAULT_HOST),\n'
                '        "debug": DEBUG,\n'
                '    }\n'
            )
        },
        "test_suite": {
            "test_get_config": (
                'def test_get_config():\n'
                '    config = get_config()\n'
                '    assert "port" in config\n'
                '    assert "host" in config\n'
                '    assert "debug" in config\n'
                '    assert isinstance(config["port"], int)\n'
                '    return True\n'
            ),
        },
    })

    return episodes


# ═══════════════════════════════════════════════════════════════════════════════
# TASK MEDIUM — Concurrent Function Modification
# ═══════════════════════════════════════════════════════════════════════════════

def generate_medium_episodes() -> List[Dict[str, Any]]:
    """Generate medium-level episodes: concurrent function modifications."""
    episodes = []

    # ── Episode 1: One branch adds validation, other adds logging ──
    episodes.append({
        "seed": 42,
        "conflicted_files": {
            "user_service.py": (
                'import logging\n'
                '\n'
                'logger = logging.getLogger(__name__)\n'
                '\n'
                '\n'
                'class UserService:\n'
                '    """Service for managing user accounts."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def create_user(self, username, email, age=None):\n'
                '        """Create a new user account."""\n'
                '<<<<<<< HEAD\n'
                '        # Validate inputs\n'
                '        if not username or len(username) < 3:\n'
                '            raise ValueError("Username must be at least 3 characters")\n'
                '        if not email or "@" not in email:\n'
                '            raise ValueError("Invalid email address")\n'
                '        if age is not None and (age < 0 or age > 150):\n'
                '            raise ValueError("Age must be between 0 and 150")\n'
                '\n'
                '        user = {"username": username, "email": email, "age": age}\n'
                '        self.db.insert("users", user)\n'
                '        return user\n'
                '=======\n'
                '        logger.info(f"Creating user: {username} ({email})")\n'
                '\n'
                '        user = {"username": username, "email": email, "age": age}\n'
                '\n'
                '        try:\n'
                '            self.db.insert("users", user)\n'
                '            logger.info(f"User created successfully: {username}")\n'
                '        except Exception as e:\n'
                '            logger.error(f"Failed to create user {username}: {e}")\n'
                '            raise\n'
                '\n'
                '        return user\n'
                '>>>>>>> feature/add-logging\n'
                '\n'
                '    def get_user(self, username):\n'
                '        """Retrieve a user by username."""\n'
                '        return self.db.find("users", {"username": username})\n'
                '\n'
                '    def delete_user(self, username):\n'
                '        """Delete a user account."""\n'
                '        return self.db.delete("users", {"username": username})\n'
            )
        },
        "git_log_ours": [
            "aaa1234 Add input validation to create_user",
            "bbb5678 Validate age parameter bounds",
        ],
        "git_log_theirs": [
            "ccc9abc Add structured logging to UserService",
            "ddddef0 Add error handling with logging in create_user",
        ],
        "ground_truth": {
            "user_service.py": (
                'import logging\n'
                '\n'
                'logger = logging.getLogger(__name__)\n'
                '\n'
                '\n'
                'class UserService:\n'
                '    """Service for managing user accounts."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def create_user(self, username, email, age=None):\n'
                '        """Create a new user account."""\n'
                '        # Validate inputs\n'
                '        if not username or len(username) < 3:\n'
                '            raise ValueError("Username must be at least 3 characters")\n'
                '        if not email or "@" not in email:\n'
                '            raise ValueError("Invalid email address")\n'
                '        if age is not None and (age < 0 or age > 150):\n'
                '            raise ValueError("Age must be between 0 and 150")\n'
                '\n'
                '        logger.info(f"Creating user: {username} ({email})")\n'
                '\n'
                '        user = {"username": username, "email": email, "age": age}\n'
                '\n'
                '        try:\n'
                '            self.db.insert("users", user)\n'
                '            logger.info(f"User created successfully: {username}")\n'
                '        except Exception as e:\n'
                '            logger.error(f"Failed to create user {username}: {e}")\n'
                '            raise\n'
                '\n'
                '        return user\n'
                '\n'
                '    def get_user(self, username):\n'
                '        """Retrieve a user by username."""\n'
                '        return self.db.find("users", {"username": username})\n'
                '\n'
                '    def delete_user(self, username):\n'
                '        """Delete a user account."""\n'
                '        return self.db.delete("users", {"username": username})\n'
            )
        },
        "test_suite": {
            "test_create_user_valid": (
                'def test_create_user_valid():\n'
                '    class MockDB:\n'
                '        def __init__(self): self.data = []\n'
                '        def insert(self, coll, doc): self.data.append(doc)\n'
                '        def find(self, coll, q): return next((d for d in self.data if d["username"] == q["username"]), None)\n'
                '        def delete(self, coll, q): self.data = [d for d in self.data if d["username"] != q["username"]]\n'
                '    svc = UserService(MockDB())\n'
                '    user = svc.create_user("alice", "alice@example.com", age=30)\n'
                '    assert user["username"] == "alice"\n'
                '    assert user["email"] == "alice@example.com"\n'
                '    return True\n'
            ),
            "test_create_user_invalid_username": (
                'def test_create_user_invalid_username():\n'
                '    class MockDB:\n'
                '        def insert(self, c, d): pass\n'
                '    svc = UserService(MockDB())\n'
                '    try:\n'
                '        svc.create_user("ab", "a@b.com")\n'
                '        return False  # Should have raised\n'
                '    except ValueError:\n'
                '        return True\n'
            ),
            "test_create_user_invalid_email": (
                'def test_create_user_invalid_email():\n'
                '    class MockDB:\n'
                '        def insert(self, c, d): pass\n'
                '    svc = UserService(MockDB())\n'
                '    try:\n'
                '        svc.create_user("alice", "not-email")\n'
                '        return False\n'
                '    except ValueError:\n'
                '        return True\n'
            ),
            "test_logging_present": (
                'def test_logging_present():\n'
                '    """Verify that logging calls are present in the code."""\n'
                '    import inspect\n'
                '    source = inspect.getsource(UserService.create_user)\n'
                '    has_logging = "logger.info" in source or "logger.error" in source\n'
                '    return has_logging\n'
            ),
        },
    })

    # ── Episode 2: One branch adds caching, other adds retry logic ──
    episodes.append({
        "seed": 123,
        "conflicted_files": {
            "api_client.py": (
                'import time\n'
                '\n'
                '\n'
                'class APIClient:\n'
                '    """HTTP API client with configurable base URL."""\n'
                '\n'
                '    def __init__(self, base_url, timeout=30):\n'
                '        self.base_url = base_url.rstrip("/")\n'
                '        self.timeout = timeout\n'
                '\n'
                '    def get(self, endpoint, params=None):\n'
                '        """Make a GET request to the API."""\n'
                '<<<<<<< HEAD\n'
                '        # Simple cache using dict\n'
                '        cache_key = f"{endpoint}:{params}"\n'
                '        if not hasattr(self, "_cache"):\n'
                '            self._cache = {}\n'
                '        if cache_key in self._cache:\n'
                '            entry = self._cache[cache_key]\n'
                '            if time.time() - entry["time"] < 60:  # 60s TTL\n'
                '                return entry["data"]\n'
                '\n'
                '        url = f"{self.base_url}/{endpoint}"\n'
                '        response = self._request("GET", url, params=params)\n'
                '\n'
                '        self._cache[cache_key] = {"data": response, "time": time.time()}\n'
                '        return response\n'
                '=======\n'
                '        url = f"{self.base_url}/{endpoint}"\n'
                '        max_retries = 3\n'
                '        for attempt in range(max_retries):\n'
                '            try:\n'
                '                response = self._request("GET", url, params=params)\n'
                '                return response\n'
                '            except ConnectionError:\n'
                '                if attempt == max_retries - 1:\n'
                '                    raise\n'
                '                time.sleep(2 ** attempt)  # Exponential backoff\n'
                '>>>>>>> feature/retry-logic\n'
                '\n'
                '    def _request(self, method, url, params=None):\n'
                '        """Simulate an HTTP request."""\n'
                '        return {"status": 200, "url": url, "method": method}\n'
            )
        },
        "git_log_ours": [
            "eee1111 Add in-memory cache to GET requests",
            "fff2222 Set 60-second TTL on cache entries",
        ],
        "git_log_theirs": [
            "ggg3333 Add retry logic with exponential backoff",
            "hhh4444 Handle ConnectionError in GET requests",
        ],
        "ground_truth": {
            "api_client.py": (
                'import time\n'
                '\n'
                '\n'
                'class APIClient:\n'
                '    """HTTP API client with configurable base URL."""\n'
                '\n'
                '    def __init__(self, base_url, timeout=30):\n'
                '        self.base_url = base_url.rstrip("/")\n'
                '        self.timeout = timeout\n'
                '\n'
                '    def get(self, endpoint, params=None):\n'
                '        """Make a GET request to the API."""\n'
                '        # Simple cache using dict\n'
                '        cache_key = f"{endpoint}:{params}"\n'
                '        if not hasattr(self, "_cache"):\n'
                '            self._cache = {}\n'
                '        if cache_key in self._cache:\n'
                '            entry = self._cache[cache_key]\n'
                '            if time.time() - entry["time"] < 60:  # 60s TTL\n'
                '                return entry["data"]\n'
                '\n'
                '        url = f"{self.base_url}/{endpoint}"\n'
                '        max_retries = 3\n'
                '        for attempt in range(max_retries):\n'
                '            try:\n'
                '                response = self._request("GET", url, params=params)\n'
                '                self._cache[cache_key] = {"data": response, "time": time.time()}\n'
                '                return response\n'
                '            except ConnectionError:\n'
                '                if attempt == max_retries - 1:\n'
                '                    raise\n'
                '                time.sleep(2 ** attempt)  # Exponential backoff\n'
                '\n'
                '    def _request(self, method, url, params=None):\n'
                '        """Simulate an HTTP request."""\n'
                '        return {"status": 200, "url": url, "method": method}\n'
            )
        },
        "test_suite": {
            "test_get_basic": (
                'def test_get_basic():\n'
                '    client = APIClient("https://api.example.com")\n'
                '    result = client.get("users")\n'
                '    assert result["status"] == 200\n'
                '    return True\n'
            ),
            "test_cache_hit": (
                'def test_cache_hit():\n'
                '    client = APIClient("https://api.example.com")\n'
                '    r1 = client.get("users")\n'
                '    r2 = client.get("users")\n'
                '    assert r1 == r2\n'
                '    # Second call should use cache\n'
                '    has_cache = hasattr(client, "_cache")\n'
                '    return has_cache\n'
            ),
            "test_retry_on_error": (
                'def test_retry_on_error():\n'
                '    """Check that retry logic exists in source."""\n'
                '    import inspect\n'
                '    source = inspect.getsource(APIClient.get)\n'
                '    has_retry = "max_retries" in source or "attempt" in source\n'
                '    return has_retry\n'
            ),
        },
    })

    # ── Episode 3: One adds pagination, other adds filtering ──
    episodes.append({
        "seed": 256,
        "conflicted_files": {
            "data_store.py": (
                'class DataStore:\n'
                '    """In-memory data store with query capabilities."""\n'
                '\n'
                '    def __init__(self):\n'
                '        self.collections = {}\n'
                '\n'
                '    def insert(self, collection, document):\n'
                '        """Insert a document into a collection."""\n'
                '        if collection not in self.collections:\n'
                '            self.collections[collection] = []\n'
                '        self.collections[collection].append(document)\n'
                '\n'
                '    def query(self, collection, **kwargs):\n'
                '        """Query documents from a collection."""\n'
                '<<<<<<< HEAD\n'
                '        docs = self.collections.get(collection, [])\n'
                '        # Add pagination support\n'
                '        page = kwargs.get("page", 1)\n'
                '        page_size = kwargs.get("page_size", 10)\n'
                '        start = (page - 1) * page_size\n'
                '        end = start + page_size\n'
                '        return {\n'
                '            "data": docs[start:end],\n'
                '            "total": len(docs),\n'
                '            "page": page,\n'
                '            "page_size": page_size,\n'
                '        }\n'
                '=======\n'
                '        docs = self.collections.get(collection, [])\n'
                '        # Add filtering support\n'
                '        filters = kwargs.get("filters", {})\n'
                '        for key, value in filters.items():\n'
                '            docs = [d for d in docs if d.get(key) == value]\n'
                '        return {"data": docs, "total": len(docs)}\n'
                '>>>>>>> feature/add-filters\n'
            )
        },
        "git_log_ours": [
            "iii5555 Add pagination to DataStore.query",
        ],
        "git_log_theirs": [
            "jjj6666 Add filtering support to DataStore.query",
        ],
        "ground_truth": {
            "data_store.py": (
                'class DataStore:\n'
                '    """In-memory data store with query capabilities."""\n'
                '\n'
                '    def __init__(self):\n'
                '        self.collections = {}\n'
                '\n'
                '    def insert(self, collection, document):\n'
                '        """Insert a document into a collection."""\n'
                '        if collection not in self.collections:\n'
                '            self.collections[collection] = []\n'
                '        self.collections[collection].append(document)\n'
                '\n'
                '    def query(self, collection, **kwargs):\n'
                '        """Query documents from a collection."""\n'
                '        docs = self.collections.get(collection, [])\n'
                '        # Add filtering support\n'
                '        filters = kwargs.get("filters", {})\n'
                '        for key, value in filters.items():\n'
                '            docs = [d for d in docs if d.get(key) == value]\n'
                '        # Add pagination support\n'
                '        page = kwargs.get("page", 1)\n'
                '        page_size = kwargs.get("page_size", 10)\n'
                '        start = (page - 1) * page_size\n'
                '        end = start + page_size\n'
                '        return {\n'
                '            "data": docs[start:end],\n'
                '            "total": len(docs),\n'
                '            "page": page,\n'
                '            "page_size": page_size,\n'
                '        }\n'
            )
        },
        "test_suite": {
            "test_insert_and_query": (
                'def test_insert_and_query():\n'
                '    store = DataStore()\n'
                '    store.insert("users", {"name": "Alice", "age": 30})\n'
                '    result = store.query("users")\n'
                '    assert len(result["data"]) == 1\n'
                '    return True\n'
            ),
            "test_pagination": (
                'def test_pagination():\n'
                '    store = DataStore()\n'
                '    for i in range(25):\n'
                '        store.insert("items", {"id": i})\n'
                '    result = store.query("items", page=2, page_size=10)\n'
                '    assert len(result["data"]) == 10\n'
                '    assert result["page"] == 2\n'
                '    return True\n'
            ),
            "test_filtering": (
                'def test_filtering():\n'
                '    store = DataStore()\n'
                '    store.insert("users", {"name": "Alice", "role": "admin"})\n'
                '    store.insert("users", {"name": "Bob", "role": "user"})\n'
                '    result = store.query("users", filters={"role": "admin"})\n'
                '    assert len(result["data"]) == 1\n'
                '    assert result["data"][0]["name"] == "Alice"\n'
                '    return True\n'
            ),
        },
    })

    return episodes


# ═══════════════════════════════════════════════════════════════════════════════
# TASK HARD — Cross-Module Refactor Collision
# ═══════════════════════════════════════════════════════════════════════════════

def generate_hard_episodes() -> List[Dict[str, Any]]:
    """Generate hard-level episodes: cross-module refactor collisions."""
    episodes = []

    # ── Episode 1: Module refactor vs new feature using old API ──
    episodes.append({
        "seed": 42,
        "conflicted_files": {
            "models.py": (
                '"""Data models for the application."""\n'
                '\n'
                '\n'
                '<<<<<<< HEAD\n'
                'class BaseEntity:\n'
                '    """Base class for all entities with common fields."""\n'
                '\n'
                '    def __init__(self, entity_id, created_at=None):\n'
                '        self.entity_id = entity_id\n'
                '        self.created_at = created_at\n'
                '\n'
                '    def to_dict(self):\n'
                '        return {"entity_id": self.entity_id, "created_at": self.created_at}\n'
                '\n'
                '\n'
                'class User(BaseEntity):\n'
                '    """User model with extracted base class."""\n'
                '\n'
                '    def __init__(self, entity_id, name, email, created_at=None):\n'
                '        super().__init__(entity_id, created_at)\n'
                '        self.name = name\n'
                '        self.email = email\n'
                '\n'
                '    def to_dict(self):\n'
                '        d = super().to_dict()\n'
                '        d.update({"name": self.name, "email": self.email})\n'
                '        return d\n'
                '\n'
                '\n'
                'class Product(BaseEntity):\n'
                '    """Product model with extracted base class."""\n'
                '\n'
                '    def __init__(self, entity_id, title, price, created_at=None):\n'
                '        super().__init__(entity_id, created_at)\n'
                '        self.title = title\n'
                '        self.price = price\n'
                '\n'
                '    def to_dict(self):\n'
                '        d = super().to_dict()\n'
                '        d.update({"title": self.title, "price": self.price})\n'
                '        return d\n'
                '=======\n'
                'class User:\n'
                '    """User model."""\n'
                '\n'
                '    def __init__(self, user_id, name, email):\n'
                '        self.user_id = user_id\n'
                '        self.name = name\n'
                '        self.email = email\n'
                '\n'
                '    def to_dict(self):\n'
                '        return {"user_id": self.user_id, "name": self.name, "email": self.email}\n'
                '\n'
                '\n'
                'class Product:\n'
                '    """Product model."""\n'
                '\n'
                '    def __init__(self, product_id, title, price):\n'
                '        self.product_id = product_id\n'
                '        self.title = title\n'
                '        self.price = price\n'
                '\n'
                '    def to_dict(self):\n'
                '        return {"product_id": self.product_id, "title": self.title, "price": self.price}\n'
                '\n'
                '\n'
                'class Order:\n'
                '    """New order model for the checkout feature."""\n'
                '\n'
                '    def __init__(self, order_id, user_id, items, total):\n'
                '        self.order_id = order_id\n'
                '        self.user_id = user_id\n'
                '        self.items = items  # list of product_ids\n'
                '        self.total = total\n'
                '\n'
                '    def to_dict(self):\n'
                '        return {\n'
                '            "order_id": self.order_id,\n'
                '            "user_id": self.user_id,\n'
                '            "items": self.items,\n'
                '            "total": self.total,\n'
                '        }\n'
                '>>>>>>> feature/checkout\n'
            ),
            "service.py": (
                '"""Business logic services."""\n'
                '\n'
                '<<<<<<< HEAD\n'
                'from models import User, Product, BaseEntity\n'
                '\n'
                '\n'
                'class EntityService:\n'
                '    """Generic service for all entities."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def save(self, entity):\n'
                '        """Save any entity to the database."""\n'
                '        if not isinstance(entity, BaseEntity):\n'
                '            raise TypeError("Expected a BaseEntity instance")\n'
                '        data = entity.to_dict()\n'
                '        collection = type(entity).__name__.lower() + "s"\n'
                '        self.db.insert(collection, data)\n'
                '        return data\n'
                '\n'
                '    def find_by_id(self, entity_class, entity_id):\n'
                '        """Find an entity by its ID."""\n'
                '        collection = entity_class.__name__.lower() + "s"\n'
                '        return self.db.find(collection, {"entity_id": entity_id})\n'
                '=======\n'
                'from models import User, Product, Order\n'
                '\n'
                '\n'
                'class UserService:\n'
                '    """Service for user operations."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def create_user(self, user_id, name, email):\n'
                '        user = User(user_id, name, email)\n'
                '        self.db.insert("users", user.to_dict())\n'
                '        return user\n'
                '\n'
                '\n'
                'class OrderService:\n'
                '    """Service for order/checkout operations."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def create_order(self, order_id, user_id, product_ids, prices):\n'
                '        total = sum(prices)\n'
                '        order = Order(order_id, user_id, product_ids, total)\n'
                '        self.db.insert("orders", order.to_dict())\n'
                '        return order\n'
                '\n'
                '    def get_user_orders(self, user_id):\n'
                '        return self.db.find_all("orders", {"user_id": user_id})\n'
                '>>>>>>> feature/checkout\n'
            ),
            "app.py": (
                '"""Main application entry point."""\n'
                '\n'
                '<<<<<<< HEAD\n'
                'from models import User, Product\n'
                'from service import EntityService\n'
                '\n'
                '\n'
                'def setup_app(db):\n'
                '    """Initialize the application."""\n'
                '    service = EntityService(db)\n'
                '    return service\n'
                '\n'
                '\n'
                'def create_sample_data(service):\n'
                '    """Create sample data using the entity service."""\n'
                '    user = User("u1", "Alice", "alice@example.com")\n'
                '    product = Product("p1", "Widget", 9.99)\n'
                '    service.save(user)\n'
                '    service.save(product)\n'
                '    return user, product\n'
                '=======\n'
                'from models import User, Product, Order\n'
                'from service import UserService, OrderService\n'
                '\n'
                '\n'
                'def setup_app(db):\n'
                '    """Initialize the application with all services."""\n'
                '    user_svc = UserService(db)\n'
                '    order_svc = OrderService(db)\n'
                '    return user_svc, order_svc\n'
                '\n'
                '\n'
                'def create_sample_data(user_svc, order_svc):\n'
                '    """Create sample data with checkout flow."""\n'
                '    user = user_svc.create_user("u1", "Alice", "alice@example.com")\n'
                '    order = order_svc.create_order("o1", "u1", ["p1", "p2"], [9.99, 19.99])\n'
                '    return user, order\n'
                '>>>>>>> feature/checkout\n'
            ),
        },
        "git_log_ours": [
            "xxx1111 Extract BaseEntity class from User and Product",
            "xxx2222 Create generic EntityService with save/find_by_id",
            "xxx3333 Refactor app.py to use EntityService",
        ],
        "git_log_theirs": [
            "yyy4444 Add Order model for checkout feature",
            "yyy5555 Add OrderService with create_order and get_user_orders",
            "yyy6666 Update app.py with checkout flow",
        ],
        "ground_truth": {
            "models.py": (
                '"""Data models for the application."""\n'
                '\n'
                '\n'
                'class BaseEntity:\n'
                '    """Base class for all entities with common fields."""\n'
                '\n'
                '    def __init__(self, entity_id, created_at=None):\n'
                '        self.entity_id = entity_id\n'
                '        self.created_at = created_at\n'
                '\n'
                '    def to_dict(self):\n'
                '        return {"entity_id": self.entity_id, "created_at": self.created_at}\n'
                '\n'
                '\n'
                'class User(BaseEntity):\n'
                '    """User model with extracted base class."""\n'
                '\n'
                '    def __init__(self, entity_id, name, email, created_at=None):\n'
                '        super().__init__(entity_id, created_at)\n'
                '        self.name = name\n'
                '        self.email = email\n'
                '\n'
                '    def to_dict(self):\n'
                '        d = super().to_dict()\n'
                '        d.update({"name": self.name, "email": self.email})\n'
                '        return d\n'
                '\n'
                '\n'
                'class Product(BaseEntity):\n'
                '    """Product model with extracted base class."""\n'
                '\n'
                '    def __init__(self, entity_id, title, price, created_at=None):\n'
                '        super().__init__(entity_id, created_at)\n'
                '        self.title = title\n'
                '        self.price = price\n'
                '\n'
                '    def to_dict(self):\n'
                '        d = super().to_dict()\n'
                '        d.update({"title": self.title, "price": self.price})\n'
                '        return d\n'
                '\n'
                '\n'
                'class Order(BaseEntity):\n'
                '    """Order model for the checkout feature."""\n'
                '\n'
                '    def __init__(self, entity_id, user_id, items, total, created_at=None):\n'
                '        super().__init__(entity_id, created_at)\n'
                '        self.user_id = user_id\n'
                '        self.items = items\n'
                '        self.total = total\n'
                '\n'
                '    def to_dict(self):\n'
                '        d = super().to_dict()\n'
                '        d.update({\n'
                '            "user_id": self.user_id,\n'
                '            "items": self.items,\n'
                '            "total": self.total,\n'
                '        })\n'
                '        return d\n'
            ),
            "service.py": (
                '"""Business logic services."""\n'
                '\n'
                'from models import User, Product, Order, BaseEntity\n'
                '\n'
                '\n'
                'class EntityService:\n'
                '    """Generic service for all entities."""\n'
                '\n'
                '    def __init__(self, db):\n'
                '        self.db = db\n'
                '\n'
                '    def save(self, entity):\n'
                '        """Save any entity to the database."""\n'
                '        if not isinstance(entity, BaseEntity):\n'
                '            raise TypeError("Expected a BaseEntity instance")\n'
                '        data = entity.to_dict()\n'
                '        collection = type(entity).__name__.lower() + "s"\n'
                '        self.db.insert(collection, data)\n'
                '        return data\n'
                '\n'
                '    def find_by_id(self, entity_class, entity_id):\n'
                '        """Find an entity by its ID."""\n'
                '        collection = entity_class.__name__.lower() + "s"\n'
                '        return self.db.find(collection, {"entity_id": entity_id})\n'
                '\n'
                '    def find_all(self, entity_class, filters=None):\n'
                '        """Find all entities matching filters."""\n'
                '        collection = entity_class.__name__.lower() + "s"\n'
                '        return self.db.find_all(collection, filters or {})\n'
            ),
            "app.py": (
                '"""Main application entry point."""\n'
                '\n'
                'from models import User, Product, Order\n'
                'from service import EntityService\n'
                '\n'
                '\n'
                'def setup_app(db):\n'
                '    """Initialize the application."""\n'
                '    service = EntityService(db)\n'
                '    return service\n'
                '\n'
                '\n'
                'def create_sample_data(service):\n'
                '    """Create sample data including checkout flow."""\n'
                '    user = User("u1", "Alice", "alice@example.com")\n'
                '    product = Product("p1", "Widget", 9.99)\n'
                '    service.save(user)\n'
                '    service.save(product)\n'
                '    order = Order("o1", "u1", ["p1", "p2"], 29.98)\n'
                '    service.save(order)\n'
                '    return user, product, order\n'
            ),
        },
        "test_suite": {
            "test_base_entity": (
                'def test_base_entity():\n'
                '    """BaseEntity class should exist with entity_id."""\n'
                '    e = BaseEntity("e1")\n'
                '    assert e.entity_id == "e1"\n'
                '    assert "entity_id" in e.to_dict()\n'
                '    return True\n'
            ),
            "test_user_inherits_base": (
                'def test_user_inherits_base():\n'
                '    u = User("u1", "Alice", "alice@example.com")\n'
                '    assert isinstance(u, BaseEntity)\n'
                '    d = u.to_dict()\n'
                '    assert d["name"] == "Alice"\n'
                '    assert "entity_id" in d\n'
                '    return True\n'
            ),
            "test_order_exists": (
                'def test_order_exists():\n'
                '    """Order class should exist and work."""\n'
                '    o = Order("o1", "u1", ["p1"], 9.99)\n'
                '    d = o.to_dict()\n'
                '    assert "items" in d\n'
                '    assert d["total"] == 9.99\n'
                '    return True\n'
            ),
            "test_order_inherits_base": (
                'def test_order_inherits_base():\n'
                '    """Order should inherit from BaseEntity."""\n'
                '    o = Order("o1", "u1", ["p1"], 9.99)\n'
                '    assert isinstance(o, BaseEntity)\n'
                '    assert "entity_id" in o.to_dict()\n'
                '    return True\n'
            ),
            "test_entity_service_saves": (
                'def test_entity_service_saves():\n'
                '    class MockDB:\n'
                '        def __init__(self): self.data = {}\n'
                '        def insert(self, coll, doc):\n'
                '            self.data.setdefault(coll, []).append(doc)\n'
                '        def find(self, coll, q): return None\n'
                '        def find_all(self, coll, q): return self.data.get(coll, [])\n'
                '    db = MockDB()\n'
                '    svc = EntityService(db)\n'
                '    u = User("u1", "Alice", "alice@example.com")\n'
                '    svc.save(u)\n'
                '    assert len(db.data.get("users", [])) == 1\n'
                '    return True\n'
            ),
            "test_setup_app": (
                'def test_setup_app():\n'
                '    class MockDB:\n'
                '        def insert(self, c, d): pass\n'
                '        def find(self, c, q): return None\n'
                '        def find_all(self, c, q): return []\n'
                '    service = setup_app(MockDB())\n'
                '    assert service is not None\n'
                '    return True\n'
            ),
        },
    })

    return episodes


# ═══════════════════════════════════════════════════════════════════════════════
# Generate & save all task files
# ═══════════════════════════════════════════════════════════════════════════════

def generate_all_tasks():
    """Generate all task JSON files."""
    tasks_dir = Path(__file__).parent / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    task_generators = {
        "easy": generate_easy_episodes,
        "medium": generate_medium_episodes,
        "hard": generate_hard_episodes,
    }

    for task_id, generator in task_generators.items():
        episodes = generator()
        task_data = {
            "task_id": task_id,
            "description": _get_task_description(task_id),
            "episodes": episodes,
        }

        output_path = tasks_dir / f"task_{task_id}.json"
        with open(output_path, "w") as f:
            json.dump(task_data, f, indent=2)
        print(f"Generated {output_path} with {len(episodes)} episodes")


def _get_task_description(task_id: str) -> str:
    descriptions = {
        "easy": (
            "Whitespace / Comment Conflict: Two branches modify only formatting, "
            "comments, or blank lines in the same function. No semantic change. "
            "Agent must pick or merge trivially."
        ),
        "medium": (
            "Concurrent Function Modification: Both branches modify the same function "
            "body with different but compatible logic (e.g., one adds validation, "
            "other adds logging). Agent must synthesize both changes."
        ),
        "hard": (
            "Cross-Module Refactor Collision: One branch refactors a module (extracts "
            "base classes, renames functions), other adds new features using the old API. "
            "Conflicts span multiple files. Agent must reconcile architecture + preserve "
            "new features."
        ),
    }
    return descriptions.get(task_id, "Unknown task")


if __name__ == "__main__":
    generate_all_tasks()
