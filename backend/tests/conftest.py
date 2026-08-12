import os

# Tests never read or mutate the developer's application database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-with-at-least-32-characters"
